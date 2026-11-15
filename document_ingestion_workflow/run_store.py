"""Durable SQLite run and event storage shared by the API and worker."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, database: Path | None = None) -> None:
        configured = os.getenv("INGESTION_STATE_DB")
        self.database = database or Path(
            configured
            or Path(__file__).resolve().parents[1] / "crawl_dir" / "state" / "ingestion.sqlite3"
        )
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id          TEXT PRIMARY KEY,
                    document        TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    last_event_seq  INTEGER NOT NULL DEFAULT 0,
                    error           TEXT,
                    created_at      TEXT NOT NULL,
                    started_at      TEXT,
                    finished_at     TEXT,
                    updated_at      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    run_id      TEXT NOT NULL,
                    seq         INTEGER NOT NULL,
                    event_type  TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    PRIMARY KEY (run_id, seq),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS events_by_run
                    ON events(run_id, seq);
                """
            )

    def create(self, run_id: str, document: str) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, document, status, created_at, updated_at
                ) VALUES (?, ?, 'queued', ?, ?)
                """,
                (run_id, document, now, now),
            )

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row is not None else None

    def mark_running(self, run_id: str) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = 'running',
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE run_id = ?
                  AND status NOT IN ('succeeded', 'failed', 'cancelled')
                """,
                (now, now, run_id),
            )

    def append_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT last_event_seq FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown run: {run_id}")
            seq = int(row["last_event_seq"]) + 1
            stored = {**event, "seq": seq, "at": now}
            connection.execute(
                """
                INSERT INTO events (run_id, seq, event_type, payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, seq, str(event.get("type", "event")), json.dumps(stored), now),
            )
            connection.execute(
                """
                UPDATE runs
                SET last_event_seq = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (seq, now, run_id),
            )
        return stored

    def finish(self, run_id: str, status: str, error: dict[str, Any] | None = None) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid terminal status: {status}")
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET status = ?, error = ?, finished_at = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, json.dumps(error) if error else None, now, now, run_id),
            )

    def snapshot(self, run_id: str, offset: int) -> tuple[list[dict[str, Any]], bool]:
        with self._connect() as connection:
            run = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(f"Unknown run: {run_id}")
            rows = connection.execute(
                """
                SELECT payload
                FROM events
                WHERE run_id = ? AND seq > ?
                ORDER BY seq
                """,
                (run_id, offset),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows], run["status"] in TERMINAL_STATUSES


class DurableRun:
    """The event-sink interface expected by the existing ingestion agent."""

    def __init__(self, store: RunStore, run_id: str) -> None:
        self.store = store
        self.run_id = run_id
        self._failed = False
        self._error: dict[str, Any] | None = None

    def emit(self, event: dict[str, Any]) -> None:
        if event.get("type") == "agent_started":
            self.store.mark_running(self.run_id)
        if event.get("type") == "agent_error":
            self._failed = True
            self._error = event
        self.store.append_event(self.run_id, event)

    def finish(self) -> None:
        self.store.finish(
            self.run_id,
            "failed" if self._failed else "succeeded",
            self._error,
        )
