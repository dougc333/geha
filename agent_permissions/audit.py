"""Audit log: one JSON line per permission decision.

Path: the `path` argument, else $AGENT_PERMISSIONS_AUDIT_LOG, else
~/.cache/agent_permissions/audit.jsonl. `records` keeps the decisions in memory too (tests,
UIs). A failed write is reported on the `agent_permissions` logger but never turns a DENY
into anything else; the middleware treats a failed write before an ALLOW as a reason to deny.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("agent_permissions")
DEFAULT_PATH = Path.home() / ".cache" / "agent_permissions" / "audit.jsonl"


class AuditLog:
    def __init__(self, path: str | Path | None = None, *, write: bool = True):
        self.path = Path(path or os.environ.get("AGENT_PERMISSIONS_AUDIT_LOG") or DEFAULT_PATH)
        self.write = write
        self.records: list[dict] = []
        self._lock = threading.Lock()

    def record(self, **fields) -> dict:
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **fields}
        with self._lock:
            self.records.append(entry)
            if self.write:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, default=str) + "\n")
        log.info("permission %s %s/%s: %s", entry.get("decision"), entry.get("agent"), entry.get("tool"),
                 entry.get("reason"))
        return entry


class MemoryAuditLog(AuditLog):
    """In-memory only (tests)."""

    def __init__(self):
        super().__init__(Path(os.devnull), write=False)
