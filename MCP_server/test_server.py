"""Safeguard and real stdio-protocol tests. All outputs stay in temporary dirs."""

import asyncio
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from flow_service import FLOWS, FlowService

ROOT = Path(__file__).resolve().parent


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "source"
        for f in FLOWS.values():
            (self.source / f.folder).mkdir(parents=True)
            shutil.copy2(ROOT / f.folder / f.script, self.source / f.folder / f.script)
        self.claims = self.base / "audit.json"
        self.claims.write_text(
            json.dumps([{"claim_id": "CLM-100005", "final_status": "PAID"}])
        )
        self.service = FlowService(
            self.source, self.base / "runs", self.claims, timeout=5
        )

    def replace_script(self, code, key="01"):
        f = FLOWS[key]
        (self.source / f.folder / f.script).write_text(code)

    async def test_all_flows_and_provenance(self):
        result = await self.service.execute(list(FLOWS))
        self.assertEqual(result["execution_order"], list(FLOWS))
        rid = result["run_id"]
        status = self.service.manifest(rid)[1]
        self.assertEqual(status["claims_snapshot"]["records"], 1)
        self.assertEqual(
            result["results"]["09"]["summary"]["evidence_files_present"], 9
        )
        self.assertFalse(result["results"]["09"]["compliance_verified"])
        records = self.service.records("08", rid, "records")["items"]
        self.assertTrue(
            any(r["resolution"] == "Claim CLM-100005 status: PAID" for r in records)
        )
        self.assertEqual(len(list(self.source.glob("*/mcp_response.json"))), 0)
        events = self.service.records("01", rid, "events", 0, 2)
        self.assertEqual(len(events["items"]), 2)
        self.assertEqual(events["next_offset"], 2)

    async def test_prerequisites_and_parallel_isolation(self):
        a, b = await asyncio.gather(
            self.service.execute(["04"]), self.service.execute(["04"])
        )
        self.assertNotEqual(a["run_id"], b["run_id"])
        self.assertEqual(a["execution_order"], ["01", "04"])
        self.assertEqual(a["results"]["04"]["summary"], b["results"]["04"]["summary"])

    async def test_unknown_flow_and_path_rejected(self):
        for key in ("../01", "10", "01;echo hi"):
            with self.assertRaises(ValueError):
                await self.service.execute([key])
        with self.assertRaises(ValueError):
            self.service.manifest("../anything")
        self.assertFalse(self.service.runs.exists())

    async def test_missing_claims_warning(self):
        self.claims.unlink()
        result = await self.service.execute(["09"])
        self.assertTrue(result["warnings"])
        self.assertEqual(
            result["results"]["09"]["summary"]["evidence_files_missing"], 1
        )

    async def test_stale_template_not_returned(self):
        folder = self.source / FLOWS["01"].folder
        (folder / "mcp_response.json").write_text('{"execution_status":"completed"}')
        self.replace_script('print("no response produced")')
        with self.assertRaises(RuntimeError):
            await self.service.execute(["01"])
        (work,) = self.service.runs.glob("run_*")
        self.assertEqual(self.service.manifest(work.name)[1]["status"], "failed")
        with self.assertRaises(ValueError):
            self.service.result("01", work.name)

    async def test_nonzero_exit(self):
        self.replace_script("raise SystemExit(7)")
        with self.assertRaisesRegex(RuntimeError, "status 7"):
            await self.service.execute(["01"])

    async def test_timeout(self):
        self.service.timeout = 0.1
        self.replace_script("import time; time.sleep(10)")
        with self.assertRaises(RuntimeError):
            await self.service.execute(["01"])
        (work,) = self.service.runs.glob("run_*")
        self.assertEqual(self.service.manifest(work.name)[1]["status"], "failed")

    async def test_log_limit(self):
        self.replace_script('print("x" * 300000)')
        with self.assertRaisesRegex(RuntimeError, "log size"):
            await self.service.execute(["01"])

    async def test_symlink_source(self):
        path = self.source / FLOWS["01"].folder / FLOWS["01"].script
        path.unlink()
        path.symlink_to(ROOT / FLOWS["01"].folder / FLOWS["01"].script)
        with self.assertRaisesRegex(RuntimeError, "escapes"):
            await self.service.execute(["01"])

    async def test_quota(self):
        self.service.max_runs = 0
        with self.assertRaisesRegex(RuntimeError, "quota"):
            await self.service.execute(["01"])

    async def test_bad_pagination(self):
        result = await self.service.execute(["01"])
        for offset, limit in [(-1, 10), (0, 101), (0, 0)]:
            with self.assertRaises(ValueError):
                self.service.records("01", result["run_id"], "events", offset, limit)

    async def test_invalid_payload(self):
        self.replace_script(
            'from pathlib import Path; Path("mcp_response.json").write_text("{}")'
        )
        with self.assertRaisesRegex(RuntimeError, "invalid simulator response"):
            await self.service.execute(["01"])

    async def test_busy(self):
        await self.service.slots.acquire()
        await self.service.slots.acquire()
        try:
            with self.assertRaisesRegex(RuntimeError, "busy"):
                await self.service.execute(["01"])
        finally:
            self.service.slots.release()
            self.service.slots.release()

    async def test_cancellation(self):
        self.replace_script("import time; time.sleep(10)")
        task = asyncio.create_task(self.service.execute(["01"]))
        await asyncio.sleep(0.1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        (work,) = self.service.runs.glob("run_*")
        self.assertEqual(self.service.manifest(work.name)[1]["status"], "cancelled")


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            params = StdioServerParameters(
                command=sys.executable,
                args=[str(ROOT / "server.py")],
                env={
                    "GEHA_RUNS_DIR": tmp,
                    "GEHA_CLAIMS_PATH": str(Path(tmp) / "missing.json"),
                },
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    self.assertEqual(
                        {t.name for t in tools},
                        {
                            "list_flows",
                            "run_flow",
                            "run_all_flows",
                            "get_flow_results",
                            "get_flow_records",
                            "get_flow_events",
                            "get_run_status",
                        },
                    )
                    listed = await session.call_tool("list_flows", {})
                    self.assertFalse(listed.isError)
                    self.assertEqual(len(listed.structuredContent["flows"]), 9)
                    invalid = await session.call_tool(
                        "run_flow", {"flow_id": "../../etc"}
                    )
                    self.assertTrue(invalid.isError)
                    result = await session.call_tool("run_all_flows", {})
                    self.assertFalse(result.isError)
                    payload = result.structuredContent
                    self.assertEqual(len(payload["results"]), 9)
                    rid = payload["run_id"]
                    for key in FLOWS:
                        read_result = await session.call_tool(
                            "get_flow_results", {"flow_id": key, "run_id": rid}
                        )
                        self.assertFalse(read_result.isError)
                        self.assertEqual(read_result.structuredContent["run_id"], rid)
                    events = await session.call_tool(
                        "get_flow_events", {"flow_id": "01", "run_id": rid, "limit": 2}
                    )
                    self.assertEqual(len(events.structuredContent["items"]), 2)
                    bad = await session.call_tool(
                        "get_flow_results", {"flow_id": "01", "run_id": "../bad"}
                    )
                    self.assertTrue(bad.isError)


if __name__ == "__main__":
    unittest.main()
