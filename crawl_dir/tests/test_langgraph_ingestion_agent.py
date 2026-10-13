"""A LangGraph agent that uses the document ingestion pipeline through MCP.

The graph is real (model node -> ToolNode -> model node); the tools come from the
geha-ingestion MCP server started as a stdio subprocess; a scripted model stands in
for the LLM, so no model is called.

    cd /Users/dc/geha
    uv run --no-sync --with 'mcp>=1.2,<2' --with langchain-mcp-adapters --with langgraph \
        python -m unittest crawl_dir.tests.test_langgraph_ingestion_agent -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

REPO = Path(__file__).resolve().parents[2]
EY_DOCUMENT = "ey-limra-workforce-benefits-study-final-2025.pdf"
EY_PDF = REPO / "crawl_dir" / "raw" / "research" / EY_DOCUMENT


class ScriptedModel:
    """Stands in for an LLM: plays back AIMessages and records what it was shown."""

    def __init__(self, *replies: AIMessage) -> None:
        self.replies, self.seen, self.bound_tools = list(replies), [], []

    def bind_tools(self, tools, **_kwargs):
        self.bound_tools = [tool.name for tool in tools]
        return self

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


async def run_agent(question: str, model: ScriptedModel) -> dict:
    """Connect to the ingestion MCP server, build the graph, and answer one question."""
    client = MultiServerMCPClient({"ingestion": {
        "command": sys.executable,
        "args": ["-m", "crawl_dir.src.ingestion_mcp"],
        "cwd": str(REPO),
        "transport": "stdio",
    }})
    tools = await client.get_tools()
    bound = model.bind_tools(tools)

    async def agent(state: MessagesState) -> dict:
        return {"messages": [await bound.ainvoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    result = await graph.compile().ainvoke({"messages": [HumanMessage(question)]})
    return {"answer": result["messages"][-1].content, "messages": result["messages"]}


def tool_results(result: dict) -> list[ToolMessage]:
    return [message for message in result["messages"] if isinstance(message, ToolMessage)]


def _text(message: ToolMessage) -> str:
    content = message.content
    if isinstance(content, list):  # content blocks from the MCP adapter
        return "".join(block.get("text", "") for block in content if isinstance(block, dict))
    return str(content)


class IngestionAgentTests(unittest.TestCase):
    def test_agent_sees_the_pipeline_tools(self):
        model = ScriptedModel(AIMessage("I can list, download and ingest public PDFs."))
        asyncio.run(run_agent("What can you do?", model))
        self.assertIn("ingest_pdf_with_figure_specs", model.bound_tools)
        self.assertIn("list_public_pdfs", model.bound_tools)

    def test_agent_finds_a_document_with_the_pipeline_catalog(self):
        model = ScriptedModel(
            tool_call("list_public_pdfs", {"query": "datroway"}),
            AIMessage("Found the Datroway coverage policy."),
        )
        result = asyncio.run(run_agent("Is there a Datroway policy?", model))
        self.assertIn("geha-coverage-policy-datroway.pdf", _text(tool_results(result)[0]))
        self.assertEqual(result["answer"], "Found the Datroway coverage policy.")

    @unittest.skipUnless(EY_PDF.is_file(), "needs the EY report under crawl_dir/raw")
    def test_agent_previews_figure_spec_ingestion_before_running_it(self):
        args = {"family": "research", "document": EY_DOCUMENT,
                "document_version": "2025", "data_classification": "public"}
        model = ScriptedModel(
            tool_call("ingest_pdf_with_figure_specs", args),
            AIMessage("20 pages have figure specs; confirm to ingest."),
        )
        result = asyncio.run(run_agent("Ingest the EY report with figure specs", model))
        preview = json.loads(_text(tool_results(result)[0]))
        self.assertEqual(preview["status"], "approval_required")
        self.assertEqual(len(preview["spec_pages"]), 20)
        self.assertIsNone(preview["model"])

    def test_pipeline_errors_reach_the_model(self):
        args = {"family": "coverage-policies", "document": "geha-coverage-policy-datroway.pdf",
                "document_version": "test", "data_classification": "public"}
        model = ScriptedModel(
            tool_call("ingest_pdf_with_figure_specs", args),
            AIMessage("That document has no figure specs."),
        )
        result = asyncio.run(run_agent("Ingest Datroway with figure specs", model))
        error = _text(tool_results(result)[0])
        self.assertTrue("No figure specs" in error or "Error" in error, error)
        self.assertEqual(result["answer"], "That document has no figure specs.")


if __name__ == "__main__":
    unittest.main()
