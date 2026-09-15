"""Integration test: run all flows in isolation and verify response counters.

Run: python -m unittest discover -s /Users/dc/geha/highlevel_simulation -p test_responses.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class MCPResponsesTest(unittest.TestCase):
    def test_all_flows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folders = sorted(ROOT.glob("0[1-9]_*"))
            self.assertEqual(len(folders), 9)
            for folder in folders:
                shutil.copytree(
                    folder,
                    root / folder.name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            for folder in sorted(root.glob("0[1-9]_*")):
                with self.subTest(flow=folder.name):
                    target = folder / "mcp_response.json"
                    target.unlink(missing_ok=True)
                    (script,) = folder.glob("simulate_*.py")
                    subprocess.run(
                        [sys.executable, str(script)],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    response = json.loads(target.read_text())
                    self.assertEqual(response["flow"], folder.name)
                    self.assertFalse(response["example_only"])
                    self.assertTrue(response["simulation_only"])
                    self.assertEqual(response["execution_status"], "completed")
                    records, events = [
                        json.loads((folder / f).read_text())
                        for f in response["outputs"]
                    ]
                    s = response["summary"]
                    number = int(folder.name[:2])
                    total_keys = {
                        1: "members_created",
                        2: "providers_processed",
                        3: "requests_processed",
                        4: "members_processed",
                        5: "appeals_processed",
                        6: "claims_screened",
                        7: "candidates_processed",
                        8: "inquiries_processed",
                    }
                    if number in total_keys:
                        self.assertEqual(s[total_keys[number]], len(records))
                    mappings = {
                        3: (
                            "decision",
                            {
                                "approved": "APPROVED",
                                "denied": "DENIED",
                                "pending_review": "PENDING_REVIEW",
                                "no_auth_needed": "NO_AUTH_NEEDED",
                                "not_covered": "NOT_COVERED",
                            },
                        ),
                        4: (
                            "status",
                            {
                                "current": "CURRENT",
                                "past_due": "PAST_DUE",
                                "lapsed": "LAPSED",
                            },
                        ),
                        5: (
                            "final",
                            {
                                "final_upheld": "UPHELD",
                                "final_overturned": "OVERTURNED",
                            },
                        ),
                        6: (
                            "decision",
                            {
                                "clean": "CLEAN",
                                "fraud_referred": "FRAUD_REFERRED",
                                "adjusted": "ADJUSTED",
                                "overpayment_recovered": "OVERPAYMENT_RECOVERED",
                                "error_corrected": "ERROR_CORRECTED",
                            },
                        ),
                        7: (
                            "status",
                            {
                                "declined": "DECLINED",
                                "monitoring": "MONITORING",
                                "completed": "COMPLETED",
                            },
                        ),
                        8: (
                            "status",
                            {
                                "reported_resolved": "RESOLVED",
                                "unresolved": "UNRESOLVED",
                                "escalated": "ESCALATED",
                            },
                        ),
                    }
                    if number in mappings:
                        field, mapping = mappings[number]
                        counts = Counter(r[field] for r in records)
                        for key, status in mapping.items():
                            self.assertEqual(s[key], counts[status])
                    if number == 1:
                        self.assertEqual(
                            s["active_members"],
                            sum(r["status"] == "ACTIVE" for r in records),
                        )
                        self.assertEqual(
                            s["coverage_changes"],
                            sum(e["stage"] == "MAINTENANCE" for e in events),
                        )
                    elif number == 2:
                        good = [r for r in records if r["status"] == "CREDENTIALED"]
                        self.assertEqual(s["credentialed"], len(good))
                        self.assertEqual(
                            s["rejected"],
                            sum(r["status"] == "REJECTED" for r in records),
                        )
                        self.assertEqual(
                            s["in_network"],
                            sum(r["network"] == "IN_NETWORK" for r in good),
                        )
                        self.assertEqual(
                            s["out_of_network"],
                            sum(r["network"] == "OUT_OF_NETWORK" for r in good),
                        )
                    elif number == 5:
                        self.assertEqual(
                            s["rejected_late"],
                            sum(bool(r["filed_late"]) for r in records),
                        )
                        self.assertEqual(
                            s["escalated_to_external_review"],
                            sum(bool(r["escalated"]) for r in records),
                        )
                    elif number == 9:
                        self.assertEqual(
                            s,
                            {
                                "evidence_files_expected": 9,
                                "evidence_files_present": 8,
                                "evidence_files_missing": 1,
                            },
                        )
                        self.assertFalse(response["compliance_verified"])
                    if number in (8, 9):
                        self.assertTrue(response["warnings"])


if __name__ == "__main__":
    unittest.main()
