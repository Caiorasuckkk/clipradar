"""SQLite-backed persistence for the DarkFlow job queue (Bloco A).

State/index for background jobs lives here so long-running work (render, voice,
script generation) is durable, retryable and pollable without blocking FastAPI.
Heavy media (mp4/mp3/assets) stays on disk under storage/generation/*.

Design notes:
- WAL mode so a worker thread can write while request threads read.
- All writes are serialized through a process-wide lock; SQLite + a single
  background worker means contention is negligible, and the lock keeps the
  "claim next job" step race-free if a second worker is ever added.
- Connections are short-lived (opened per operation) to avoid cross-thread
  sqlite handle sharing.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app import config


_WRITE_LOCK = threading.Lock()
_INITIALIZED = False
_INIT_LOCK = threading.Lock()


_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        project_id TEXT,
        payload TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'queued',
        progress REAL NOT NULL DEFAULT 0,
        step TEXT NOT NULL DEFAULT '',
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 1,
        priority INTEGER NOT NULL DEFAULT 0,
        cancel_requested INTEGER NOT NULL DEFAULT 0,
        pid INTEGER,
        result TEXT,
        error TEXT,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type)",
    "CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id)",
)


def _db_path() -> Path:
    path = config.STORAGE_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db() -> None:
    """Create the schema once. Safe to call repeatedly and from any thread."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    with _INIT_LOCK:
        if _INITIALIZED:
            return
        with _connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            for statement in _SCHEMA_STATEMENTS:
                conn.execute(statement)
            conn.commit()
        _INITIALIZED = True


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(_db_path()), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def mutate(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Run a write statement under the global write lock. Returns rowcount."""
    init_db()
    with _WRITE_LOCK:
        with _connect() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount


@contextmanager
def write_transaction() -> Iterator[sqlite3.Connection]:
    """Exclusive write transaction for multi-statement atomic operations
    (e.g. claim-next-job: SELECT a queued row then UPDATE it to running)."""
    init_db()
    with _WRITE_LOCK:
        with _connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise


def to_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return "{}"


def from_json(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
