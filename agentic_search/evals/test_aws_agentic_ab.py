"""Unit tests for AWS agentic A/B metric helpers; no AWS calls."""

import unittest

from aws_agentic_ab import canonical_source, markdown_report, summarize


class AwsAgenticAbTest(unittest.TestCase):
    def test_canonical_source_ignores_arxiv_version_suffix(self):
        self.assertEqual(canonical_source("1706.03762v7.pdf"), "1706.03762.pdf")
        self.assertEqual(canonical_source("doc.pdf"), "doc.pdf")

    def test_summary_and_markdown_report(self):
        row = {
            "fact_total": 2,
            "fact_recall": 1.0,
            "source_recall": 1.0,
            "complete": True,
            "grounded": True,
            "correct_abstention": False,
            "retrieval_rounds": 1,
            "used_followup": False,
            "generation_attempts": 1,
            "latency_ms": 100.0,
        }
        summary = summarize([row])
        report = markdown_report({"single_search": summary, "corrective": summary})
        self.assertEqual(summary["fact_recall"], 1.0)
        self.assertIn("| Fact recall | 100.0% | 100.0% | +0.0 pp |", report)


if __name__ == "__main__":
    unittest.main()
