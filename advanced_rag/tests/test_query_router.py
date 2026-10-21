from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aws_data_workflow.query_router import (
    list_router_runs,
    load_clusters,
    parse_jsonl,
    route_jsonl,
    save_router_run,
)


class QueryRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.manifest = Path(self.temporary.name) / "clusters.json"
        self.manifest.write_text(json.dumps({
            "documents": [
                {"path": "policy.pdf", "cluster": "policy"},
                {"path": "benefits.pdf", "cluster": "benefits_research"},
                {"path": "study.pdf", "cluster": "research"},
            ],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_cluster_inventory_includes_empty_known_clusters(self) -> None:
        clusters = {item["id"]: item for item in load_clusters(self.manifest)}
        self.assertEqual(len(clusters), 6)
        self.assertEqual(clusters["policy"]["document_count"], 1)
        self.assertEqual(clusters["clinical_guidance"]["document_count"], 0)

    def test_routes_benefits_query_with_visible_evidence(self) -> None:
        result = route_jsonl(
            '{"user_input":"Which employer benefits survey reports premium changes?"}',
            self.manifest,
        )
        self.assertEqual(result["status"], "routed")
        route = result["routes"][0]
        self.assertEqual(route["cluster"], "benefits_research")
        self.assertIn("employer", route["signals"])
        self.assertEqual(route["destination"], "cluster/benefits_research")

    def test_routes_employer_population_sdoh_query_to_benefits(self) -> None:
        result = route_jsonl(
            '{"user_input":"What percentage of adults in the HAC employer-plan population have high SDOH risk?"}',
            self.manifest,
        )
        route = result["routes"][0]
        self.assertEqual(route["cluster"], "benefits_research")
        self.assertIn("employer", route["signals"])

    def test_routes_health_plan_premium_allocation_to_policy(self) -> None:
        result = route_jsonl(
            '{"user_input":"How is a commercial health plan premium typically allocated across different categories of health care spending?"}',
            self.manifest,
        )
        route = result["routes"][0]
        self.assertEqual(route["cluster"], "policy")
        self.assertIn("health plan premium", route["signals"])

    def test_routes_medicare_affordability_analysis_to_research(self) -> None:
        result = route_jsonl(
            '{"user_input":"According to the ASPE data-point analysis, which groups of Medicare beneficiaries are most likely to experience problems affording prescription medications?"}',
            self.manifest,
        )
        route = result["routes"][0]
        self.assertEqual(route["cluster"], "research")
        self.assertIn("analysis", route["signals"])

    def test_routes_pickleball_study_outcomes_to_research(self) -> None:
        result = route_jsonl(
            '{"user_input":"According to the ACE-sponsored six-week Pickleball study, what cardiovascular and metabolic changes were observed in middle-aged and older adults?"}',
            self.manifest,
        )
        route = result["routes"][0]
        self.assertEqual(route["cluster"], "research")
        self.assertIn("study", route["signals"])

    def test_accepts_multiple_jsonl_query_field_names(self) -> None:
        records = parse_jsonl(
            '{"query":"Is this service covered?"}\n'
            '{"question":"Where is the application form?"}\n'
        )
        self.assertEqual(records, [(1, "Is this service covered?"), (2, "Where is the application form?")])

    def test_invalid_jsonl_returns_failed_validation_event(self) -> None:
        result = route_jsonl('{"query":', self.manifest)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["events"][-1]["status"], "failed")
        self.assertIn("Line 1", result["error"])

    def test_saved_run_can_be_restored(self) -> None:
        result = route_jsonl('{"query":"Is this service covered?"}', self.manifest)
        saved = save_router_run(Path(self.temporary.name), '{"query":"Is this service covered?"}', result)
        history = list_router_runs(Path(self.temporary.name))
        self.assertEqual(history[0]["run_id"], saved["run_id"])
        self.assertEqual(history[0]["input_jsonl"], '{"query":"Is this service covered?"}')
        self.assertEqual(history[0]["routes"][0]["cluster"], "policy")


if __name__ == "__main__":
    unittest.main()
