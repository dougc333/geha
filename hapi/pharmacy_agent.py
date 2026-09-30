#!/usr/bin/env python3
"""Pharmacy-review agent: one LangGraph agent over three MCP servers.

    fhir     langcare-mcp-fhir -> local HAPI (synthetic Synthea members)   read-only tools
    rxnorm   @pipeworx/mcp-rxnorm (local stdio) -> NLM RxNav                drug normalization
    openfda  @cyanheads/openfda-mcp-server (local stdio) -> openFDA         recalls, shortages, labels

All three run as local stdio processes: member data stays on this Mac, and the drug
look-ups go straight to the public NLM and FDA APIs (no hosted gateway in between).
Graph and model come from langgraph_agent.build_graph. Needs Node (npx) for the two
drug servers.

    ANTHROPIC_API_KEY=... python pharmacy_agent.py ["your question"]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from langgraph_agent import build_graph

HERE = Path(__file__).resolve().parent
QUIET = {"PATH": os.environ["PATH"], "MCP_TRANSPORT_TYPE": "stdio", "MCP_LOG_LEVEL": "error"}
SERVERS = {
    "fhir": {"transport": "stdio", "command": str(HERE / "bin" / "langcare-mcp-fhir"),
             "args": ["-config", str(HERE / "langcare-config.yaml")]},
    "rxnorm": {"transport": "stdio", "command": "npx", "args": ["-y", "@pipeworx/mcp-rxnorm@0.1.2"],
               "env": QUIET},
    "openfda": {"transport": "stdio", "command": "npx", "args": ["-y", "@cyanheads/openfda-mcp-server@0.7.9"],
                "env": QUIET},
}
# Tools offered to the model. FHIR: read-only. openFDA: the drug-safety subset.
ALLOWED = {
    "fhir": {"fhir_search", "fhir_read"},
    "rxnorm": {"rxnorm_search", "rxnorm_get_properties", "rxnorm_related", "rxnorm_ndc"},
    "openfda": {"openfda_drug_profile", "openfda_search_recalls", "openfda_search_drug_shortages",
                "openfda_get_drug_label", "openfda_lookup_ndc"},
}
QUESTION = ("Pharmacy review for our members with type 2 diabetes: list each one's active "
            "medications. For each distinct drug, give the RxNorm ingredient, and check FDA "
            "for a current drug shortage and for recalls since 2025-01-01. Finish with the "
            "items a pharmacy-benefit team should act on.")
SYSTEM = ("You are a health-plan pharmacy analyst. Member data comes from a FHIR R4 server "
          "with synthetic (Synthea) members, via fhir_search and fhir_read (SNOMED 44054006 = "
          "type 2 diabetes; MedicationRequest?patient=...&status=active for active drugs). Use "
          "the rxnorm_* tools to normalize drugs to RxNorm ingredients and the openfda_* tools "
          "for shortages, recalls and labels. Check each distinct drug once, not once per "
          "member. Report FDA findings with their dates, recall class and status, say 'none "
          "found' when a search returns nothing, and don't infer anything the data doesn't "
          "show. The members are synthetic; the FDA data is real.")


async def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    client = MultiServerMCPClient(SERVERS)
    tools = []
    for server, allowed in ALLOWED.items():
        tools += [t for t in await client.get_tools(server_name=server) if t.name in allowed]
    print(f"Tools bound to Claude ({len(tools)}): {[t.name for t in tools]}\n\nQ: {question}\n")

    app = build_graph(tools, system=SYSTEM)
    calls, final = 0, None
    async for update in app.astream({"messages": [("user", question)]}, stream_mode="updates",
                                    config={"recursion_limit": 100}):
        for output in update.values():
            for message in output["messages"]:
                if isinstance(message, AIMessage) and message.tool_calls:
                    for call in message.tool_calls:
                        calls += 1
                        print(f"  [{calls}] {call['name']} {call['args']}")
                elif isinstance(message, ToolMessage) and message.status == "error":
                    print(f"      error from {message.name}: {str(message.content)[:200]}")
                elif isinstance(message, AIMessage):
                    final = message
    print("\nA:", final.text if final else "(no answer)")
    print(f"\n({calls} tool calls across FHIR, RxNorm and openFDA)")


if __name__ == "__main__":
    asyncio.run(main())
