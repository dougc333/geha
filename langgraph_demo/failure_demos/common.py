"""Shared disposable fixtures for failure demonstrations."""

from __future__ import annotations

import json
from pathlib import Path


CONFIG = {"configurable": {"thread_id": "failure-demo"}}


def write_synthetic_inputs(base: Path) -> None:
    """Create the smallest valid input tree used by demo.make_graph()."""
    claims = base / "demo_data"
    claims.mkdir(parents=True)
    (claims / "claims.json").write_text(
        json.dumps(
            [
                {
                    "claim_id": "CLM-FAILURE-DEMO",
                    "member_id": "MEMBER-DEMO",
                    "plan": "Synthetic failure plan",
                }
            ]
        )
    )
    (claims / "audit_trails.json").write_text(
        json.dumps(
            [
                {
                    "claim_id": "CLM-FAILURE-DEMO",
                    "final_status": "PENDING_REVIEW",
                    "stages": [
                        {"status": "PENDING", "note": "Prior authorization review"}
                    ],
                }
            ]
        )
    )
    (claims / "public_reference.json").write_text("[]")


def receive(pipe, expected: str, timeout: float = 15.0):
    if not pipe.poll(timeout):
        raise TimeoutError(f"Worker did not send {expected!r} within {timeout}s")
    kind, value = pipe.recv()
    if kind != expected:
        raise RuntimeError(f"Worker returned {kind}: {value}")
    return value


def stop_process(process) -> None:
    if process.is_alive():
        process.kill()
    process.join(5)
    if process.is_alive():
        raise RuntimeError("Worker did not terminate")
