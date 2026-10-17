"""Tests for generation-evaluation helpers."""

import unittest

from context_assembly_benchmarks.generation_eval import summary_rate


class SummaryRateTest(unittest.TestCase):
    def test_reads_current_nested_schema(self):
        summary = {
            "flat": {"overall": {"judge_yes_rate": 0.25}},
            "flat_answer_yes_rate": 0.75,
        }

        self.assertEqual(
            summary_rate(
                summary,
                path="flat",
                metric="judge_yes_rate",
                legacy_key="flat_answer_yes_rate",
            ),
            0.25,
        )

    def test_falls_back_to_legacy_schema(self):
        self.assertEqual(
            summary_rate(
                {"flat_answer_yes_rate": 0.75},
                path="flat",
                metric="judge_yes_rate",
                legacy_key="flat_answer_yes_rate",
            ),
            0.75,
        )

    def test_missing_rate_defaults_to_zero(self):
        self.assertEqual(
            summary_rate(
                {},
                path="flat",
                metric="judge_yes_rate",
                legacy_key="flat_answer_yes_rate",
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
