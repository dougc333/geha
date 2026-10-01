"""Pure unit tests for retrieval-eval cost accounting."""

import importlib.util
import math
import unittest
from pathlib import Path


PATH = Path(__file__).parents[1] / "evals" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("run_eval", PATH)
run_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_eval)


class SearchUnitsTest(unittest.TestCase):
    def test_rounds_each_request_up_to_one_hundred_candidates(self):
        self.assertEqual(run_eval.search_units(0), 0)
        self.assertEqual(run_eval.search_units(1), 1)
        self.assertEqual(run_eval.search_units(50), 1)
        self.assertEqual(run_eval.search_units(100), 1)
        self.assertEqual(run_eval.search_units(101), 2)

    def test_rejects_negative_candidate_count(self):
        with self.assertRaises(ValueError):
            run_eval.search_units(-1)


class CostSummaryTest(unittest.TestCase):
    def test_records_observed_calls_without_inventing_embedding_tokens(self):
        result = run_eval.cost_summary(
            representation="combined-table-figure",
            question_count=62,
            embedding_calls=62,
            rerank_calls=186,
            rerank_search_units=186,
            embedding_model="embed",
            rerank_model="rerank",
            rerank_price_per_unit=0.001,
            started_at="start",
            finished_at="finish",
        )
        self.assertEqual(result["rerank"]["estimated_cost_usd"], 0.186)
        self.assertIsNone(result["embedding"]["input_tokens"])
        self.assertIsNone(result["embedding"]["estimated_cost_usd"])


class RetrievalMetricsTest(unittest.TestCase):
    GOLD = {"document_id": 7, "page": 3}

    @staticmethod
    def ranked(gold_rank: int | None) -> list[dict]:
        rows = [{"document_id": 99, "page": rank} for rank in range(1, 11)]
        if gold_rank is not None:
            rows[gold_rank - 1] = {"document_id": 7, "page": 3}
        return rows

    def test_rank_one_has_perfect_retrieval_metrics(self):
        result = run_eval.metrics(self.ranked(1), self.GOLD)
        self.assertEqual(result["recall5"], 1.0)
        self.assertEqual(result["rr"], 1.0)
        self.assertEqual(result["ndcg10"], 1.0)

    def test_rank_five_is_recalled_and_discounted(self):
        result = run_eval.metrics(self.ranked(5), self.GOLD)
        self.assertEqual(result["recall5"], 1.0)
        self.assertAlmostEqual(result["rr"], 0.2)
        self.assertAlmostEqual(result["ndcg10"], 1 / math.log2(6))

    def test_missing_gold_has_zero_retrieval_metrics(self):
        result = run_eval.metrics(self.ranked(None), self.GOLD)
        self.assertEqual(result["recall5"], 0.0)
        self.assertEqual(result["rr"], 0.0)
        self.assertEqual(result["ndcg10"], 0.0)


if __name__ == "__main__":
    unittest.main()
