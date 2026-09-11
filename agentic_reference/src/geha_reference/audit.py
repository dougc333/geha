from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    audit_id: str
    timestamp: str
    actor_id: str
    role: str
    action: str
    resource_ids: tuple[str, ...]
    outcome: str


class AuditLogger:
    """Append-only audit sink that deliberately excludes prompts and PHI."""

    def __init__(self, path: Path | None = None):
        self.path = path
        self.events: list[AuditEvent] = []

    def record(
        self,
        *,
        actor_id: str,
        role: str,
        action: str,
        resource_ids: tuple[str, ...] = (),
        outcome: str,
    ) -> str:
        event = AuditEvent(
            audit_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            actor_id=actor_id,
            role=role,
            action=action,
            resource_ids=resource_ids,
            outcome=outcome,
        )
        self.events.append(event)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(event)) + "\n")
        return event.audit_id

