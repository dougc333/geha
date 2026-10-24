from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aws_data_workflow.query_router import (
    _apply_routing_guardrails,
    list_router_runs,
    load_clusters,
    parse_jsonl,
    route_jsonl,
    save_router_run,
)


class QueryRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {"TYPESAFE_API_KEY": ""})
        self.environment.start()
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
        self.environment.stop()

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

    def test_semantic_overlap_guardrails_match_labeled_clusters(self) -> None:
        cases = [
            ("What percentage of the U.S. population did women ages 18-44 represent in the Health of Women and Children Report?", "population_health"),
            ("Why do most small firms continue to offer health insurance despite the ACA exemption?", "research"),
            ("How do disparities in access to employer-sponsored benefits affect employees?", "benefits_research"),
            ("How does the CMS-HCC risk adjustment model v28 affect payments?", "research"),
            ("How does rural primary-care physician supply compare to urban counties?", "research"),
            ("What changed according to the Employee Benefits Survey?", "benefits_research"),
            ("How does support for caregiving affect employee productivity?", "benefits_research"),
            ("What events lead to catastrophic claims?", "benefits_research"),
            ("How much did per-person health care spending grow?", "research"),
            ("What job benefits matter to women re-entering the workforce?", "benefits_research"),
        ]
        base = {
            "cluster": "policy",
            "confidence": 0.5,
            "method": "jev",
            "signals": [],
            "score": 0.5,
            "probabilities": {
                "policy": 0.5,
                "research": 0.2,
                "benefits_research": 0.1,
                "population_health": 0.1,
                "clinical_guidance": 0.05,
                "forms_directory": 0.05,
            },
        }
        for query, expected in cases:
            with self.subTest(query=query):
                result = _apply_routing_guardrails(query, base)
                self.assertEqual(result["cluster"], expected)


if __name__ == "__main__":
    unittest.main()
