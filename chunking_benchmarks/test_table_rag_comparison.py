import json
import unittest
from types import SimpleNamespace

from chunking_benchmarks.table_rag_comparison import (
    estimated_cost,
    exact_product_match,
    extract_products,
    parse_product_response,
    summarize,
    usage_from_response,
)


class TableRagComparisonTests(unittest.TestCase):
    def test_deterministic_extraction_normalizes_spacing_and_hyphens(self):
        table = (
            "Preference,Drug Name\n"
            "Non - Preferred,Zarxio\n"
            "Preferred,Nivestym\n"
            "Non- Preferred,Neupogen\n"
        )
        self.assertEqual(extract_products(table, "Preferred"), ["Nivestym"])
        self.assertEqual(
            extract_products(table, "Non-Preferred"), ["Zarxio", "Neupogen"]
        )

    def test_llm_json_contract(self):
        self.assertEqual(
            parse_product_response('```json\n{"products": ["Nivestym"]}\n```'),
            ["Nivestym"],
        )
        with self.assertRaises(ValueError):
            parse_product_response('{"products": "Nivestym"}')

    def test_matching_ignores_punctuation_and_case(self):
        self.assertTrue(
            exact_product_match(
                ["Nivestym (Filgrastim-AAFI)"], ["nivestym filgrastim aafi"]
            )
        )

    def test_usage_and_cost(self):
        response = SimpleNamespace(
            usage=SimpleNamespace(
                input_tokens=1_000, output_tokens=100, total_tokens=1_100
            )
        )
        usage = usage_from_response(response)
        self.assertEqual(usage, {"input": 1_000, "output": 100, "total": 1_100})
        self.assertAlmostEqual(estimated_cost(usage, 2.0, 8.0), 0.0028)
        self.assertIsNone(estimated_cost(usage, None, 8.0))

    def test_summary_compares_error_tokens_and_cost(self):
        template = {
            "deterministic": {"correct": True},
            "llm": {
                "correct": False,
                "usage": {"total": 25},
                "cost_usd": 0.001,
                "error": None,
            },
        }
        report = summarize([template, json.loads(json.dumps(template))])
        self.assertEqual(report["deterministic"]["error_rate"], 0.0)
        self.assertEqual(report["llm"]["error_rate"], 1.0)
        self.assertEqual(report["llm"]["tokens"], 50)
        self.assertEqual(report["llm"]["cost_usd"], 0.002)


if __name__ == "__main__":
    unittest.main()
