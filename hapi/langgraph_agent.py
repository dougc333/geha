#!/usr/bin/env python3
"""LangGraph version of mcp_agent_demo.py: Claude + the FHIR MCP server as a graph.

The MCP server's tools are loaded with langchain-mcp-adapters (stdio) and the agent is
an explicit LangGraph StateGraph, so the tool-selection step is visible:

    START -> agent --(tools_condition)--> tools -> agent -> ... -> END
             ^ Claude picks the tool       ^ ToolNode runs it over MCP

Only the read-only tools (fhir_search, fhir_read) are bound to the model. Synthetic
(Synthea) data only.

    ANTHROPIC_API_KEY=... python langgraph_agent.py ["your question"]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-5-5"
READ_ONLY_TOOLS = {"fhir_search", "fhir_read"}
QUESTION = ("Which patients have type 2 diabetes? For each one, give their name, age, most "
            "recent HbA1c with its date, and how many insurance claims (ExplanationOfBenefit) "
            "they have and the total amount paid across them.")
SYSTEM = ("You answer questions about a FHIR R4 server that contains synthetic (Synthea) test "
          "patients, using the fhir_search and fhir_read tools. Use standard codes (SNOMED "
          "44054006 for type 2 diabetes, LOINC 4548-4 for HbA1c). Keep searches small with "
          "_count and _elements where you can. Report numbers exactly as the data gives them "
          "and say when something isn't in the data.")


def build_graph(tools, system: str = SYSTEM):
    """agent node: Claude decides (answer, or which tools to call with which arguments).
    tools_condition: routes to the tools node if the reply has tool calls, else ends.
    tools node: runs the chosen MCP tools and appends their results."""
    model = ChatAnthropic(model=MODEL, max_tokens=16000).bind_tools(tools)

    async def agent(state: MessagesState):
        return {"messages": [await model.ainvoke([SystemMessage(system), *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    graph.add_edge("tools", "agent")
    return graph.compile()


async def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    client = MultiServerMCPClient({
        "fhir": {
            "transport": "stdio",
            "command": str(HERE / "bin" / "langcare-mcp-fhir"),
            "args": ["-config", str(HERE / "langcare-config.yaml")],
        }
    })
    tools = [t for t in await client.get_tools() if t.name in READ_ONLY_TOOLS]
    print(f"MCP tools bound to Claude: {[t.name for t in tools]}\n\nQ: {question}\n")

    app = build_graph(tools)
    calls, final = 0, None
    async for update in app.astream({"messages": [("user", question)]}, stream_mode="updates",
                                    config={"recursion_limit": 60}):
        for node, output in update.items():
            for message in output["messages"]:
                if isinstance(message, AIMessage) and message.tool_calls:
                    for call in message.tool_calls:
                        calls += 1
                        print(f"  [{calls}] agent -> {call['name']} {call['args']}")
                elif isinstance(message, ToolMessage) and message.status == "error":
                    print(f"      tools: {message.name} error: {str(message.content)[:200]}")
                elif isinstance(message, AIMessage):
                    final = message
    print("\nA:", final.text if final else "(no answer)")
    print(f"\n({calls} FHIR calls through MCP via LangGraph)")


if __name__ == "__main__":
    asyncio.run(main())
