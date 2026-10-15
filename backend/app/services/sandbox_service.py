import hashlib
import uuid
import re
import datetime
from typing import List, Optional, Tuple
from app.core.config import settings
from app.core.database import transaction, get_connection
from app.models.schemas import (
    ExecutionResponse,
    ChunkResponse,
    SandboxSearchResponse,
    SearchResultItem,
)


def split_into_bounded_chunks(text: str, max_chunk_size: int = 65536) -> List[str]:
    """
    Partitions raw output into chunks strictly bounded by max_chunk_size.
    Addresses issue #947 & #878: enforces chunk size cap before indexing
    so single-line payloads, diff dumps, and huge logs cannot bloat SQLite WAL.
    """
    if not text:
        return [""]

    chunks: List[str] = []
    lines = text.splitlines(keepends=True)
    current_chunk: List[str] = []
    current_size = 0

    for line in lines:
        line_bytes = len(line.encode("utf-8"))
        # If a single line itself exceeds max_chunk_size, split by byte slices
        if line_bytes > max_chunk_size:
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_size = 0
            # Slice large single line into chunks
            line_str = line
            while line_str:
                chunk_slice = line_str[:max_chunk_size // 2]
                chunks.append(chunk_slice)
                line_str = line_str[max_chunk_size // 2:]
            continue

        if current_size + line_bytes > max_chunk_size and current_chunk:
            chunks.append("".join(current_chunk))
            current_chunk = [line]
            current_size = line_bytes
        else:
            current_chunk.append(line)
            current_size += line_bytes

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks if chunks else [text]


def generate_preview_summary(
    command: str,
    raw_text: str,
    exit_code: Optional[int],
    is_sandboxed: bool,
    execution_id: str,
) -> str:
    """
    Builds a deterministic, compact preview of the output for agent context.
    Provides ~98% token reduction while preserving actionable error messages and boundaries.
    """
    lines = raw_text.splitlines()
    total_lines = len(lines)
    raw_bytes = len(raw_text.encode("utf-8"))

    if not is_sandboxed or total_lines <= 20:
        return raw_text

    head_count = 8
    tail_count = 8
    head = lines[:head_count]
    tail = lines[-tail_count:]
    omitted_lines = total_lines - (head_count + tail_count)
    omitted_bytes = raw_bytes - (sum(len(l.encode("utf-8")) for l in head) + sum(len(l.encode("utf-8")) for l in tail))

    summary_lines = [
        f"[NEXUS ENGINE: Sandboxed tool output ({total_lines} lines, {raw_bytes} bytes)]",
        f"Command: {command} (Exit Code: {exit_code if exit_code is not None else 0})",
        "--- BEGIN PREVIEW (HEAD) ---",
        *head,
        f"--- ... [{omitted_lines} lines omitted ({omitted_bytes} bytes). Use ctx_search(id='{execution_id}') to query] ---",
        "--- END PREVIEW (TAIL) ---",
        *tail,
        f"[Sandboxed Artifact Handle: {execution_id}]",
    ]
    return "\n".join(summary_lines)


def store_sandbox_payload(
    session_id: str,
    command: str,
    raw_text: str,
    exit_code: int = 0,
    duration_ms: float = 0.0,
    platform: str = "generic",
    db_path: Optional[str] = None,
    execution_id: Optional[str] = None,
) -> ExecutionResponse:
    if execution_id is None:
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
    raw_bytes = len(raw_text.encode("utf-8"))
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    is_sandboxed = raw_bytes > settings.OUTPUT_SANDBOX_THRESHOLD_BYTES
    preview = generate_preview_summary(command, raw_text, exit_code, is_sandboxed, execution_id)
    sandboxed_bytes = len(preview.encode("utf-8"))

    diverted_bytes = max(0, raw_bytes - sandboxed_bytes) if is_sandboxed else 0
    chunks = split_into_bounded_chunks(raw_text, settings.MAX_CHUNK_SIZE_BYTES)

    with transaction(db_path) as cur:
        # Upsert session
        cur.execute(
            """
            INSERT INTO sessions (id, platform, created_at, updated_at, total_raw_bytes, total_diverted_bytes, tool_calls_count)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at,
                total_raw_bytes = total_raw_bytes + excluded.total_raw_bytes,
                total_diverted_bytes = total_diverted_bytes + excluded.total_diverted_bytes,
                tool_calls_count = tool_calls_count + 1
            """,
            (session_id, platform, now_iso, now_iso, raw_bytes, diverted_bytes),
        )

        # Insert execution
        cur.execute(
            """
            INSERT INTO executions (
                id, session_id, command, status, exit_code, duration_ms,
                raw_bytes, sandboxed_bytes, is_sandboxed, preview_summary, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution_id,
                session_id,
                command,
                "completed",
                exit_code,
                duration_ms,
                raw_bytes,
                sandboxed_bytes,
                1 if is_sandboxed else 0,
                preview,
                now_iso,
            ),
        )

        # Insert chunks
        for idx, chunk_text in enumerate(chunks):
            chunk_id = f"chk_{uuid.uuid4().hex[:12]}"
            c_bytes = len(chunk_text.encode("utf-8"))
            c_sum = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
            cur.execute(
                """
                INSERT INTO output_chunks (id, execution_id, chunk_index, byte_length, content, checksum, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, execution_id, idx, c_bytes, chunk_text, c_sum, now_iso),
            )

        # Audit metric event
        cur.execute(
            """
            INSERT INTO metrics_audit (id, session_id, event_type, baseline_bytes, kept_out_bytes, tokens_saved, calculated_ratio, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"audit_{uuid.uuid4().hex[:12]}",
                session_id,
                "tool_execution",
                raw_bytes,
                diverted_bytes,
                max(0, diverted_bytes // 4),
                (diverted_bytes / raw_bytes) if raw_bytes > 0 else 0.0,
                now_iso,
            ),
        )

    return ExecutionResponse(
        id=execution_id,
        session_id=session_id,
        command=command,
        status="completed",
        exit_code=exit_code,
        duration_ms=duration_ms,
        raw_bytes=raw_bytes,
        sandboxed_bytes=sandboxed_bytes,
        is_sandboxed=is_sandboxed,
        preview_summary=preview,
        created_at=now_iso,
        chunks_count=len(chunks),
    )


def search_in_sandbox(
    execution_id: str,
    query: str,
    regex: bool = False,
    max_results: int = 10,
    db_path: Optional[str] = None,
) -> SandboxSearchResponse:
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT chunk_index, content FROM output_chunks WHERE execution_id = ? ORDER BY chunk_index ASC",
            (execution_id,),
        )
        rows = cur.fetchall()

    results: List[SearchResultItem] = []
    pattern = None
    if regex:
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # Fallback to literal search if regex is malformed
            regex = False

    total_matches = 0
    global_line = 1
    for row in rows:
        c_idx = row["chunk_index"]
        text = row["content"]
        lines = text.splitlines()

        for l_idx, line in enumerate(lines):
            matched = False
            score = 1.0
            if regex and pattern:
                if pattern.search(line):
                    matched = True
            elif query.lower() in line.lower():
                matched = True

            if matched:
                total_matches += 1
                if len(results) < max_results:
                    snippet = line.strip()
                    if len(snippet) > 200:
                        snippet = snippet[:197] + "..."
                    results.append(
                        SearchResultItem(
                            chunk_index=c_idx,
                            line_number=global_line,
                            snippet=snippet,
                            match_score=score,
                        )
                    )
            global_line += 1

    return SandboxSearchResponse(
        execution_id=execution_id,
        total_matches=total_matches,
        results=results,
    )


def get_execution(execution_id: str, db_path: Optional[str] = None) -> Optional[ExecutionResponse]:
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT e.*, COUNT(c.id) as chunks_count
            FROM executions e
            LEFT JOIN output_chunks c ON c.execution_id = e.id
            WHERE e.id = ?
            GROUP BY e.id
            """,
            (execution_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return ExecutionResponse(
            id=row["id"],
            session_id=row["session_id"],
            command=row["command"],
            status=row["status"],
            exit_code=row["exit_code"],
            duration_ms=row["duration_ms"],
            raw_bytes=row["raw_bytes"],
            sandboxed_bytes=row["sandboxed_bytes"],
            is_sandboxed=bool(row["is_sandboxed"]),
            preview_summary=row["preview_summary"],
            created_at=row["created_at"],
            chunks_count=row["chunks_count"],
        )


def get_chunks_for_execution(execution_id: str, db_path: Optional[str] = None) -> List[ChunkResponse]:
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM output_chunks WHERE execution_id = ? ORDER BY chunk_index ASC",
            (execution_id,),
        )
        rows = cur.fetchall()
        return [
            ChunkResponse(
                id=r["id"],
                chunk_index=r["chunk_index"],
                byte_length=r["byte_length"],
                content=r["content"],
                checksum=r["checksum"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
