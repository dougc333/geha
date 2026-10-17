"""Tests for deterministic benefit-table extraction and code resolution."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from structured_benefits import StructuredBenefitIndex


class StructuredBenefitIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(__file__).resolve().parents[2]
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from crawl_dir.src.consumer_paths import page_markdown

        cls.index = StructuredBenefitIndex.from_markdown(
            page_markdown(
                "dental",
                "fedvip/2026-geha-dental-benefits-guide.pdf",
                5,
                allow_candidate=True,
            )
        )

    def test_extracts_class_cost_rows(self):
        records = {record.benefit_class: record for record in self.index.records if "Covers" in record.description}

        self.assertEqual(records["Class A"].high_cost, "$0 Third adult cleaning included")
        self.assertEqual(records["Class A"].standard_in_network_cost, "$0")
        self.assertEqual(records["Class B"].high_cost, "20%")
        self.assertEqual(records["Class B"].standard_in_network_cost, "45%")
        self.assertEqual(records["Class C"].standard_in_network_cost, "65%")

    def test_resolves_codes_to_the_correct_class(self):
        expected = {"D1110": "Class A", "D7140": "Class B", "D3310": "Class C"}

        for code, benefit_class in expected.items():
            with self.subTest(code=code):
                resolved = self.index.resolve(f"What does {code} cost?")
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved.record.benefit_class, benefit_class)

    def test_structured_evidence_contains_source_identity(self):
        resolved = self.index.resolve("What does D1110 cost?")
        payload = json.loads(resolved.evidence_text().split("\n", 1)[1])

        self.assertEqual(payload["benefit_class"], "Class A")
        self.assertEqual(payload["standard_in_network_cost"], "$0")
        self.assertEqual(
            payload["source"],
            {
                "document_id": "geha-dental-benefits-guide",
                "plan_year": 2026,
                "page": 5,
                "section": "Dental benefit comparison",
            },
        )

    def test_unknown_code_does_not_guess_a_class(self):
        self.assertIsNone(self.index.resolve("What does D9999 cost?"))

    def test_resolves_plain_language_orthodontics_to_class_d(self):
        resolved = self.index.resolve(
            "I'm considering braces for myself under Standard. Are adults covered, "
            "what do I pay in-network, and what is the lifetime maximum?"
        )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.record.benefit_class, "Class D")
        self.assertIn("adult orthodontics", resolved.record.description)
        self.assertEqual(
            resolved.record.standard_in_network_cost,
            "50% with $2,500 lifetime maximum",
        )


if __name__ == "__main__":
    unittest.main()
