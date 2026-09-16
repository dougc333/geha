"""Discover and call tools through an actual MCP stdio client session."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(run_all: bool, policy_query: str | None, source_pdf: str | None, table_number: int | None):
    params = StdioServerParameters(
        command=sys.executable, args=[str(Path(__file__).with_name("server.py"))]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(
                "Tools:", ", ".join(t.name for t in (await session.list_tools()).tools)
            )
            if policy_query:
                name, arguments = "search_policy_evidence", {"query": policy_query}
            elif source_pdf is not None:
                name, arguments = "get_policy_evidence", {
                    "source_pdf": source_pdf,
                    "table_number": table_number,
                }
            else:
                name, arguments = ("run_all_flows" if run_all else "list_flows"), {}
            response = await session.call_tool(name, arguments)
            if response.isError:
                raise RuntimeError(str(response.content))
            print(json.dumps(response.structuredContent, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="Create one isolated run of all nine flows",
    )
    parser.add_argument("--policy-query", help="Search the existing policy RAG index")
    parser.add_argument("--source-pdf", help="Read an indexed source PDF table")
    parser.add_argument("--table-number", type=int, help="Table number for --source-pdf")
    args = parser.parse_args()
    if sum((args.run_all, bool(args.policy_query), args.source_pdf is not None)) > 1:
        parser.error("Choose only one action")
    if (args.source_pdf is None) != (args.table_number is None):
        parser.error("--source-pdf and --table-number must be used together")
    asyncio.run(main(args.run_all, args.policy_query, args.source_pdf, args.table_number))
