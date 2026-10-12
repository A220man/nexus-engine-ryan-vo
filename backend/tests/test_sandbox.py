import pytest
from app.services.sandbox_service import (
    split_into_bounded_chunks,
    generate_preview_summary,
    store_sandbox_payload,
    search_in_sandbox,
    get_execution,
    get_chunks_for_execution,
)


def test_chunk_bounding_under_limit():
    content = "line 1\nline 2\nline 3\n"
    chunks = split_into_bounded_chunks(content, max_chunk_size=1024)
    assert len(chunks) == 1
    assert chunks[0] == content


def test_chunk_bounding_oversized_payload():
    # Resolves #947 and #878: large payload chunking with hard size bound
    large_line = "A" * 1500 + "\n"
    content = large_line * 10  # 15,000 bytes
    chunks = split_into_bounded_chunks(content, max_chunk_size=2000)
    assert len(chunks) >= 8
    for chunk in chunks:
        assert len(chunk.encode("utf-8")) <= 2048


def test_preview_summary_formatting():
    lines = [f"output record line {i}" for i in range(100)]
    content = "\n".join(lines)
    preview = generate_preview_summary(
        command="test_command",
        raw_text=content,
        exit_code=0,
        is_sandboxed=True,
        execution_id="exec_test123",
    )
    assert "[NEXUS ENGINE: Sandboxed tool output" in preview
    assert "--- BEGIN PREVIEW (HEAD) ---" in preview
    assert "--- END PREVIEW (TAIL) ---" in preview
    assert "output record line 0" in preview
    assert "output record line 99" in preview
    assert "ctx_search(id='exec_test123')" in preview


def test_sandbox_storage_persistence(temp_db: str):
    content = "Error: File not found\nStack trace line 1\nStack trace line 2\n" * 20
    record = store_sandbox_payload(
        session_id="sess_alpha",
        command="pytest",
        raw_text=content,
        exit_code=1,
        duration_ms=45.2,
        db_path=temp_db,
    )
    assert record.id.startswith("exec_")
    assert record.session_id == "sess_alpha"
    assert record.exit_code == 1
    assert record.is_sandboxed is True
    assert record.chunks_count >= 1

    fetched = get_execution(record.id, db_path=temp_db)
    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.command == "pytest"

    chunks = get_chunks_for_execution(record.id, db_path=temp_db)
    assert len(chunks) == record.chunks_count
    assert chunks[0].content is not None


def test_sandbox_search_substring(temp_db: str):
    content = (
        "INFO Starting daemon\n"
        "DEBUG Connecting to database\n"
        "ERROR Failed to acquire connection lock\n"
        "INFO Retrying in 5 seconds\n"
    )
    record = store_sandbox_payload(
        session_id="sess_beta",
        command="daemon_check",
        raw_text=content,
        exit_code=1,
        db_path=temp_db,
    )
    search_res = search_in_sandbox(
        execution_id=record.id,
        query="Failed to acquire",
        db_path=temp_db,
    )
    assert search_res.total_matches == 1
    assert len(search_res.results) == 1
    assert "Failed to acquire connection lock" in search_res.results[0].snippet
    assert search_res.results[0].line_number == 3


def test_sandbox_search_regex(temp_db: str):
    content = (
        "User 101 logged in\n"
        "User 202 logged out\n"
        "System warning code=404\n"
    )
    record = store_sandbox_payload(
        session_id="sess_gamma",
        command="auth_scan",
        raw_text=content,
        exit_code=0,
        db_path=temp_db,
    )
    search_res = search_in_sandbox(
        execution_id=record.id,
        query=r"User \d+ logged",
        regex=True,
        db_path=temp_db,
    )
    assert search_res.total_matches == 2
    assert len(search_res.results) == 2
