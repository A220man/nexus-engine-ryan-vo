import sqlite3
import datetime
import json
from contextlib import contextmanager
from typing import Generator, Any, Dict, List, Optional
from app.core.config import settings


def get_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return "nexus_engine.db"


def init_db(db_path: Optional[str] = None) -> None:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            total_raw_bytes INTEGER NOT NULL DEFAULT 0,
            total_diverted_bytes INTEGER NOT NULL DEFAULT 0,
            tool_calls_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            command TEXT NOT NULL,
            status TEXT NOT NULL,
            exit_code INTEGER,
            duration_ms REAL NOT NULL DEFAULT 0.0,
            raw_bytes INTEGER NOT NULL DEFAULT 0,
            sandboxed_bytes INTEGER NOT NULL DEFAULT 0,
            is_sandboxed INTEGER NOT NULL DEFAULT 0,
            preview_summary TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS output_chunks (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            byte_length INTEGER NOT NULL,
            content TEXT NOT NULL,
            checksum TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_execution ON output_chunks(execution_id, chunk_index);

        CREATE TABLE IF NOT EXISTS metrics_audit (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            baseline_bytes INTEGER NOT NULL,
            kept_out_bytes INTEGER NOT NULL,
            tokens_saved INTEGER NOT NULL,
            calculated_ratio REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_sub TEXT NOT NULL,
            user_role TEXT NOT NULL,
            action TEXT NOT NULL,
            resource TEXT NOT NULL,
            details TEXT
        );
    """)
    conn.commit()
    conn.close()


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(db_path: Optional[str] = None) -> Generator[sqlite3.Cursor, None, None]:
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def log_audit(user_sub: str, user_role: str, action: str, resource: str, details: Optional[Dict[str, Any]] = None, db_path: Optional[str] = None) -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    detail_str = json.dumps(details) if details else None
    with transaction(db_path) as cur:
        cur.execute(
            "INSERT INTO audit_logs (timestamp, user_sub, user_role, action, resource, details) VALUES (?, ?, ?, ?, ?, ?)",
            (now_iso, user_sub, user_role, action, resource, detail_str)
        )
