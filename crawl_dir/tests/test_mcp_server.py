"""Smoke test: start the ingestion MCP server over stdio and call its tools.

Uses only calls that need no network, model, credentials or raw PDFs.
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TOOLS = {
    "list_public_pdfs",
    "download_public_pdf",
    "ingest_scanned_pdf",
    "ingest_native_pdf_with_semantic_html_charts",
    "ingest_pdf_with_figure_specs",
    "segment_document_page",
}


async def _exercise_server() -> dict:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "crawl_dir.src.ingestion_mcp"], cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        listing = await session.call_tool("list_public_pdfs", {"query": "datroway"})
        preview = await session.call_tool(
            "download_public_pdf",
            {"document": "geha-coverage-policy-datroway.pdf", "confirm": False},
        )
        missing = await session.call_tool("ingest_pdf_with_figure_specs", {
            "family": "research", "document": "does-not-exist.pdf",
            "document_version": "test", "data_classification": "public",
        })
        return {"tools": tools, "listing": listing, "preview": preview, "missing": missing}


class IngestionMcpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = asyncio.run(_exercise_server())

    def test_server_lists_every_tool(self):
        self.assertEqual({tool.name for tool in self.result["tools"].tools}, EXPECTED_TOOLS)

    def test_list_public_pdfs_finds_manifest_document(self):
        listing = self.result["listing"]
        self.assertFalse(listing.isError)
        self.assertIn("geha-coverage-policy-datroway.pdf", listing.content[0].text)

    def test_download_preview_requires_approval_without_downloading(self):
        preview = self.result["preview"]
        self.assertFalse(preview.isError)
        self.assertEqual(json.loads(preview.content[0].text)["status"], "approval_required")

    def test_ingest_tool_reports_errors_to_the_client(self):
        self.assertTrue(self.result["missing"].isError)


if __name__ == "__main__":
    unittest.main()
