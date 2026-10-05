"""GEHA benefits MCP server. The deployment's MCP_ENV decides which tools exist.

    MCP_ENV=production python server.py     # agents see only production-tier tools
    MCP_ENV=pilot      python server.py     # + pilot tools
    MCP_ENV=sandbox    python server.py     # + sandbox tools (synthetic data only)

Every call is written to the audit log (MCP_AUDIT_LOG) with PHI arguments hashed.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from registry import ToolSpec, exposed
from tools import SPECS

DEFAULT_AUDIT_LOG = Path(__file__).resolve().parents[1] / "audit" / "audit.jsonl"


def _redact(spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    """PHI tool arguments are logged as short hashes: traceable, not readable."""
    if spec.data_class != "phi":
        return arguments
    return {k: "sha256:" + hashlib.sha256(str(v).encode()).hexdigest()[:12] for k, v in arguments.items()}


def audited(spec: ToolSpec, environment: str, log_path: Path):
    """Wrap a tool so every call, success or failure, appends one audit record."""
    @functools.wraps(spec.func)
    def call(*args, **kwargs):
        started, outcome = time.perf_counter(), "ok"
        try:
            return spec.func(*args, **kwargs)
        except ValueError as error:
            # Expected input problems: the message is safe and helps the agent recover, so it is
            # passed to the client. Any other exception is a crash, whose detail the SDK hides.
            outcome = "error: ValueError"
            raise ToolError(str(error)) from error
        except Exception as error:
            outcome = f"error: {type(error).__name__}"
            raise
        finally:
            record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "env": environment,
                      "tool": spec.name, "version": spec.version, "tier": spec.tier,
                      "data_class": spec.data_class, "args": _redact(spec, kwargs), "outcome": outcome,
                      "ms": round((time.perf_counter() - started) * 1000, 1)}
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record) + "\n")
    return call


def build_server(environment: str, log_path: Path = DEFAULT_AUDIT_LOG) -> MCPServer:
    server = MCPServer(
        name="geha-benefits",
        instructions=("GEHA 2026 dental and coverage-policy tools. Answers come from GEHA's published "
                      "plan documents; cite the source each tool returns. Demo, not affiliated with GEHA."),
        version="0.1.0",
    )
    for spec in exposed(SPECS, environment):
        server.tool(
            name=spec.name,
            description=spec.description,
            annotations=ToolAnnotations(read_only_hint=spec.access == "read",
                                        destructive_hint=spec.access == "write",
                                        idempotent_hint=spec.access == "read", open_world_hint=False),
            meta=spec.metadata(),
        )(audited(spec, environment, log_path))
    return server


if __name__ == "__main__":
    build_server(os.environ.get("MCP_ENV", "production"),
                 Path(os.environ.get("MCP_AUDIT_LOG", DEFAULT_AUDIT_LOG))).run("stdio")
