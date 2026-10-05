"""Demo: an agent connects to each deployment over MCP and sees only what that tier allows.

The "agent" here is scripted (no LLM): it lists the tools of the production, pilot and
sandbox deployments, makes typical calls, tries a tool its deployment doesn't offer,
walks the write tool's human-approval step, and prints the audit trail.

    cd /Users/dc/geha/mcp_benefits_server/src
    uv run --no-project --python 3.12 --with mcp python demo_client.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER = Path(__file__).resolve().with_name("server.py")
AUDIT = Path(tempfile.mkdtemp()) / "demo_audit.jsonl"


def show(result) -> str:
    text = result.content[0].text if result.content else ""
    if result.is_error:
        return f"ERROR {text}"
    data = json.loads(text)
    return json.dumps(data if len(text) < 300 else {k: data[k] for k in list(data)[:3]}, default=str)[:300]


async def connect(environment: str, calls: list[tuple[str, dict]]) -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)],
                                   env={**os.environ, "MCP_ENV": environment, "MCP_AUDIT_LOG": str(AUDIT)})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = (await session.list_tools()).tools
        print(f"\n=== agent connected to the {environment.upper()} deployment: {len(listed)} tools")
        for tool in listed:
            meta, hints = tool.meta or {}, tool.annotations
            print(f"  - {tool.name:26} tier={meta.get('tier'):10} data={meta.get('data_class'):8} "
                  f"{'read-only' if hints and hints.read_only_hint else 'WRITE'}")
        offered = {t.name for t in listed}
        for name, arguments in calls:
            if name not in offered:
                print(f"  > {name}: not offered by this deployment, so the agent cannot call it")
                continue
            print(f"  > {name}({json.dumps(arguments)})\n    {show(await session.call_tool(name, arguments))}")


async def main() -> None:
    await connect("production", [
        ("rate_code_lookup", {"state": "MO", "zip_code": "64063"}),
        ("premium_quote", {"plan": "High", "status": "Employed", "enrollment": "Self Only",
                           "state": "MO", "zip_code": "64063"}),
        ("cdt_procedure_class", {"code": "D2740"}),
        ("coverage_policy_search", {"query": "romiplostim authorization"}),
        ("member_claims_summary", {"member_id": "M-100001"}),
    ])
    await connect("pilot", [("coverage_policy_search", {"query": "romiplostim authorization", "limit": 2})])
    await connect("sandbox", [
        ("member_claims_summary", {"member_id": "M-100001"}),
        ("submit_enrollment_change", {"member_id": "M-100001", "event": "marriage", "action": "change_plan"}),
        ("submit_enrollment_change", {"member_id": "M-100001", "event": "marriage", "action": "change_plan",
                                      "confirm": True}),
        ("cdt_procedure_class", {"code": "D0000"}),
    ])
    print(f"\n=== audit trail ({AUDIT}); PHI arguments are hashed")
    for line in AUDIT.read_text().splitlines():
        r = json.loads(line)
        print(f"  {r['env']:10} {r['tool']:26} args={json.dumps(r['args'])[:60]:62} {r['outcome']}")


if __name__ == "__main__":
    asyncio.run(main())
