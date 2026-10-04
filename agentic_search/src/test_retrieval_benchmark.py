"""Fast unit tests for retrieval metric and reporting logic."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


EVALS = Path(__file__).resolve().parents[1] / "evals"
sys.path.insert(0, str(EVALS))

from retrieval_benchmark import (  # noqa: E402
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    summarize,
    unique_source_names,
)


class RetrievalBenchmarkTests(unittest.TestCase):
    def test_document_metrics(self):
        ranked = ["wrong.pdf", "gold.pdf", "other.pdf"]
        relevant = {"gold.pdf"}
        self.assertEqual(recall_at_k(ranked, relevant, 5), 1.0)
        self.assertEqual(reciprocal_rank_at_k(ranked, relevant, 10), 0.5)
        self.assertAlmostEqual(ndcg_at_k(ranked, relevant, 10), 1.0 / 1.584962500721156)

    def test_multiple_relevant_sources_use_graded_recall_and_ideal_dcg(self):
        ranked = ["a.pdf", "noise.pdf", "b.pdf"]
        relevant = {"a.pdf", "b.pdf", "missing.pdf"}
        self.assertAlmostEqual(recall_at_k(ranked, relevant, 5), 2 / 3)
        self.assertEqual(reciprocal_rank_at_k(ranked, relevant, 10), 1.0)
        self.assertGreater(ndcg_at_k(ranked, relevant, 10), 0.0)
        self.assertLess(ndcg_at_k(ranked, relevant, 10), 1.0)

    def test_source_ranking_deduplicates_parent_chunks(self):
        docs = [
            SimpleNamespace(metadata={"source": "/tmp/a.pdf"}),
            SimpleNamespace(metadata={"source": "/tmp/a.pdf"}),
            SimpleNamespace(metadata={"source": "/tmp/b.pdf"}),
        ]
        self.assertEqual(unique_source_names(docs), ["a.pdf", "b.pdf"])

    def test_summary_uses_median_and_nearest_rank_p95(self):
        rows = [
            {
                "recall_at_5": value,
                "reciprocal_rank_at_10": value,
                "ndcg_at_10": value,
                "latency_ms": latency,
            }
            for value, latency in [(1.0, 10.0), (0.0, 20.0), (1.0, 100.0)]
        ]
        summary = summarize(rows)
        self.assertAlmostEqual(summary["Recall@5"], 2 / 3)
        self.assertEqual(summary["median_latency_ms"], 20.0)
        self.assertEqual(summary["p95_latency_ms"], 100.0)


if __name__ == "__main__":
    unittest.main()
