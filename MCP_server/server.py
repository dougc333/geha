"""Local stdio MCP interface for simulations and read-only policy evidence."""

import asyncio
import os
from pathlib import Path
from typing import Annotated, Literal, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from flow_service import FLOWS, FlowService
from policy_service import PolicyService

ROOT = Path(__file__).resolve().parent
SIMULATION_ROOT = ROOT.parent / "highlevel_simulation"
service = FlowService(
    SIMULATION_ROOT,
    Path(os.environ.get("GEHA_RUNS_DIR", ROOT / "runs")),
    Path(
        os.environ.get(
            "GEHA_CLAIMS_PATH",
            ROOT.parent / "demo_data/audit_trails.json",
        )
    ),
)
policy_service = PolicyService()
mcp = FastMCP(
    "GEHA Simulation",
    instructions=(
        "Local demo with fabricated insurance data and read-only extracted policy evidence. "
        "Not clinical, payment, identity, coverage, or compliance verification. "
        "Do not send real member or claim data. Simulation runs write isolated results; "
        "use the returned run_id for reads."
    ),
)
FlowId = Literal["01", "02", "03", "04", "05", "06", "07", "08", "09"]
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False
)


@mcp.tool(annotations=READ)
def list_flows() -> dict[str, Any]:
    """List the nine simulations, dependencies, and output filenames."""
    return service.list_flows()


@mcp.tool(annotations=WRITE)
async def run_flow(flow_id: FlowId) -> dict[str, Any]:
    """Run one simulation plus its prerequisites in a new isolated folder. Returns a run_id and actual summary. Uses fabricated data; no real insurance actions."""
    return await service.execute([flow_id])


@mcp.tool(annotations=WRITE)
async def run_all_flows() -> dict[str, Any]:
    """Run all nine simulations in dependency order in one new isolated folder. Does not execute claims adjudication; uses its existing audit snapshot."""
    return await service.execute(list(FLOWS))


@mcp.tool(annotations=READ)
def get_flow_results(flow_id: FlowId, run_id: str) -> dict[str, Any]:
    """Read a completed run's summary. Requires explicit run_id; never substitutes latest/example results."""
    return service.result(flow_id, run_id)


@mcp.tool(annotations=READ)
def get_flow_events(
    flow_id: FlowId,
    run_id: str,
    offset: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """Read a page of event records from a completed run."""
    return service.records(flow_id, run_id, "events", offset, limit)


@mcp.tool(annotations=READ)
def get_flow_records(
    flow_id: FlowId,
    run_id: str,
    offset: Annotated[int, Field(ge=0)] = 0,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    """Read a page of detailed simulator records from a completed run."""
    return service.records(flow_id, run_id, "records", offset, limit)


@mcp.tool(annotations=READ)
def get_run_status(run_id: str) -> dict[str, Any]:
    """Inspect a run manifest, including failed/cancelled status and input provenance."""
    return service.manifest(run_id)[1]


@mcp.tool(annotations=READ)
async def search_policy_evidence(
    query: Annotated[str, Field(min_length=1, max_length=500)],
    top_tables: Annotated[int, Field(ge=1, le=8)] = 5,
    candidate_rows: Annotated[int, Field(ge=5, le=100)] = 30,
) -> dict[str, Any]:
    """Search indexed policy evidence by exact billing code, policy/condition, then semantic fallback. Returns citations, not a claim decision. Never submit member identifiers."""
    return await asyncio.to_thread(
        policy_service.search, query, top_tables, candidate_rows
    )


@mcp.tool(annotations=READ)
async def get_policy_evidence(
    source_pdf: str,
    table_number: Annotated[int, Field(ge=1)],
    question: Annotated[str, Field(max_length=500)] = "",
) -> dict[str, Any]:
    """Get a complete indexed parent table and source-linked criteria by citation. source_pdf must be a filename returned by search, never a filesystem path."""
    return await asyncio.to_thread(
        policy_service.evidence, source_pdf, table_number, question
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
