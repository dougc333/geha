"""Tests for the GEHA benefits MCP server: tools, tier gating, audit, promotion rules.

    cd /Users/dc/geha/mcp_benefits_server
    uv run --no-project --python 3.12 --with mcp python -m unittest discover -s tests -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import tools  # noqa: E402
from check_promotion import existing_tests  # noqa: E402
from registry import requirements  # noqa: E402
from server import build_server  # noqa: E402


def spec(name):
    return next(s for s in tools.SPECS if s.name == name)


class ToolTests(unittest.TestCase):
    def test_rate_code_lookup(self):
        self.assertEqual(tools.rate_code_lookup("MO", "64063")["rate_code"], 2)
        with self.assertRaises(ValueError):
            tools.rate_code_lookup("ZZ", "64063")

    def test_premium_quote(self):
        quote = tools.premium_quote("High", "Employed", "Self Only", "MO", "64063")
        self.assertEqual((quote["premium"], quote["period"]), ("$21.32", "biweekly"))
        self.assertEqual(tools.premium_quote("standard", "retired", "Self Only", "MO", "64063")["period"], "monthly")
        with self.assertRaises(ValueError):
            tools.premium_quote("Gold", "Employed", "Self Only", "MO", "64063")

    def test_cdt_procedure_class(self):
        self.assertEqual(len(tools._cdt_index()), 378)
        self.assertIn("Class C", tools.cdt_procedure_class("d2740")["benefit_class"])
        self.assertIn("Class A", tools.cdt_procedure_class("D1110")["benefit_class"])
        with self.assertRaises(ValueError):
            tools.cdt_procedure_class("D0000")

    def test_coverage_policy_search(self):
        results = tools.coverage_policy_search("romiplostim authorization", 3)["results"]
        self.assertEqual(results[0]["policy"], "nplate")
        self.assertTrue(all(r["source"].startswith("downloads/coverage-policies/") for r in results))

    def test_member_claims_summary(self):
        summary = tools.member_claims_summary("M-100001")
        self.assertEqual(summary["by_category"]["preventive"]["claims"], 2)
        self.assertNotIn("name", json.dumps(summary))

    def test_submit_requires_confirmation(self):
        proposed = tools.submit_enrollment_change("M-100001", "marriage", "change_plan")
        self.assertEqual(proposed["status"], "approval_required")
        self.assertEqual(tools.submit_enrollment_change("M-100001", "marriage", "decrease_enrollment")["status"],
                         "not_permitted")
        self.assertEqual(tools.submit_enrollment_change("M-100001", "marriage", "change_plan", confirm=True)["status"],
                         "submitted_to_mock")


class GatingAndAuditTests(unittest.TestCase):
    def setUp(self):
        self.log = Path(tempfile.mkdtemp()) / "audit.jsonl"

    def names(self, environment):
        return {t.name for t in asyncio.run(build_server(environment, self.log).list_tools())}

    def test_each_environment_exposes_only_its_tiers(self):
        self.assertEqual(self.names("production"), {"rate_code_lookup", "premium_quote", "cdt_procedure_class"})
        self.assertEqual(self.names("pilot") - self.names("production"), {"coverage_policy_search"})
        self.assertEqual(self.names("sandbox") - self.names("pilot"),
                         {"member_claims_summary", "submit_enrollment_change"})

    def test_audit_hashes_phi_arguments_and_records_errors(self):
        server = build_server("sandbox", self.log)
        from mcp.server.mcpserver.exceptions import ToolError

        asyncio.run(server.call_tool("member_claims_summary", {"member_id": "M-100001"}))
        with self.assertRaises(ToolError):  # in-process; over the protocol the client gets is_error
            asyncio.run(server.call_tool("cdt_procedure_class", {"code": "D0000"}))
        records = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(records[0]["args"]["member_id"].startswith("sha256:"))
        self.assertNotIn("M-100001", self.log.read_text())
        self.assertEqual(records[1]["args"], {"code": "D0000"})
        self.assertTrue(records[1]["outcome"].startswith("error"))


class PromotionStandardTests(unittest.TestCase):
    def test_every_tool_meets_its_declared_tier(self):
        tests = existing_tests()
        for s in tools.SPECS:
            self.assertEqual(requirements(s, s.tier, tests), [], s.name)

    def test_promotions_that_must_be_blocked(self):
        tests = existing_tests()
        self.assertIn("evaluation evidence", " ".join(requirements(spec("coverage_policy_search"), "production", tests)))
        phi = " ".join(requirements(spec("member_claims_summary"), "pilot", tests))
        self.assertIn("encryption_at_rest", phi)
        self.assertIn("read-only access",
                      " ".join(requirements(spec("submit_enrollment_change"), "production", tests)))
        unowned = replace(spec("rate_code_lookup"), owner="")
        self.assertIn("a named owner", requirements(unowned, "production", tests))
        no_approval = replace(spec("submit_enrollment_change"), human_approval=False)
        self.assertIn("human approval for a write tool", requirements(no_approval, "sandbox", tests))


class EndToEndTest(unittest.TestCase):
    def test_client_over_stdio_sees_only_production_tools(self):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        log = Path(tempfile.mkdtemp()) / "audit.jsonl"

        async def run():
            params = StdioServerParameters(command=sys.executable, args=[str(SRC / "server.py")],
                                           env={**os.environ, "MCP_ENV": "production", "MCP_AUDIT_LOG": str(log)})
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                result = await session.call_tool("rate_code_lookup", {"state": "MO", "zip_code": "64063"})
                return names, result

        names, result = asyncio.run(run())
        self.assertNotIn("member_claims_summary", names)
        self.assertEqual(json.loads(result.content[0].text)["rate_code"], 2)


if __name__ == "__main__":
    unittest.main()
