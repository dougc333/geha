import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from chunking_benchmarks.chunking_compare import (
    compare_contexts,
    evidence_coverage,
    expected_values,
)
from chunking_benchmarks.eval_queries import load_eval_queries
from chunking_benchmarks.generation_eval import (
    deterministic_generation_metrics,
    reference_answer,
)
from chunking_benchmarks.llm_judge import (
    JudgeVerdict,
    flat_context,
    hierarchical_context,
)
from chunking_benchmarks.table_rag import (
    bm25_scores,
    infer_title,
    lexical_tokens,
    normalized_table,
    split_csv_tables,
)


class TableRagTests(unittest.TestCase):
    def test_two_blank_rows_separate_tables(self):
        content = "a,b\n1,2\n\n\nc,d\n3,4\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tables.csv"
            path.write_text(content, encoding="utf-8")
            tables = split_csv_tables(path)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0], [["a", "b"], ["1", "2"]])
        self.assertEqual(tables[1], [["c", "d"], ["3", "4"]])

    def test_normalizes_short_rows(self):
        headers, rows = normalized_table([["a", "b"], ["1"]])
        self.assertEqual(headers, ["a", "b"])
        self.assertEqual(rows, [["1", ""]])

    def test_infers_billing_title(self):
        self.assertEqual(
            infer_title(["Drug Name", "HCPCS Code", "Description"]),
            "Billing codes",
        )

    def test_bm25_prioritizes_exact_hcpcs_code(self):
        documents = [
            "Drug: Treanda; HCPCS Code: J9033",
            "Drug: Bendeka; HCPCS Code: J9034",
            "Advanced imaging prior authorization",
        ]
        scores = bm25_scores("Which drug uses J9033?", documents)
        self.assertEqual(max(range(len(scores)), key=scores.__getitem__), 0)
        self.assertIn("j9033", lexical_tokens(documents[0]))

    def test_loads_preference_and_relation_eval_queries(self):
        queries = load_eval_queries(Path(__file__).resolve().parent)
        kinds = {query["kind"] for query in queries}
        ids = {query["id"] for query in queries}
        self.assertEqual(len(queries), 41)
        self.assertEqual(kinds, {"Preference lookup", "Row-to-column relationship"})
        self.assertIn("bendamustine_non_preferred", ids)
        self.assertIn("bendamustine_j9036", ids)
        q5157 = next(query for query in queries if query["id"] == "xgeva_q5157")
        self.assertEqual(q5157["where"], {"hcpcscode": "Q5157"})

    def test_hierarchy_exposes_neighboring_expected_values(self):
        case = {
            "kind": "Row-to-column relationship",
            "expected": [{"drug": "Bendeka", "code": "J9034"}],
        }
        flat = [
            {
                "search_text": "Drug: Bendeka",
                "source": "policy.pdf",
            }
        ]
        parents = [
            {
                "full_csv": "Drug,Code\nBendeka,J9034\n",
                "source": "policy.pdf",
            }
        ]
        comparison = compare_contexts(flat, parents, case)
        self.assertEqual(comparison["flat"]["expected_evidence_coverage"], 0.5)
        self.assertEqual(comparison["hierarchical"]["expected_evidence_coverage"], 1.0)
        self.assertGreater(
            comparison["hierarchical"]["estimated_tokens"],
            comparison["flat"]["estimated_tokens"],
        )

    def test_expected_value_helpers_handle_preference_cases(self):
        case = {"kind": "Preference lookup", "expected": ["Treanda", "Bendeka"]}
        values = expected_values(case)
        found, total, coverage = evidence_coverage(values, "Treanda is preferred")
        self.assertEqual((found, total, coverage), (1, 2, 0.5))

    def test_llm_contexts_preserve_provenance(self):
        flat = flat_context(
            [
                {
                    "source": "policy.pdf",
                    "title": "Billing codes",
                    "row_number": 2,
                    "search_text": "Drug: Treanda; Code: J9033",
                }
            ]
        )
        hierarchy = hierarchical_context(
            [
                {
                    "source": "policy.pdf",
                    "title": "Billing codes",
                    "table_number": 1,
                    "full_csv": "Drug,Code\nTreanda,J9033\n",
                }
            ]
        )
        self.assertIn("SOURCE: policy.pdf", flat)
        self.assertIn("ROW: 2", flat)
        self.assertIn("TABLE NUMBER: 1", hierarchy)
        self.assertIn("Treanda,J9033", hierarchy)

    def test_judge_verdict_rejects_non_binary_answer(self):
        with self.assertRaises(ValidationError):
            JudgeVerdict(
                answers_query="maybe",
                grounded_in_context=True,
                reason="Ambiguous",
                missing_information=[],
            )

    def test_generation_eval_uses_reference_and_rejects_unexpected_code(self):
        case = {
            "kind": "Row-to-column relationship",
            "where": {"hcpcscode": "Q5157"},
            "expected": [
                {
                    "drugname": "Denosumab-bmwo (Osenvelt)",
                    "preference": "Non-Preferred",
                    "requirespriorauth": "Yes",
                },
                {
                    "drugname": "Denosumab-bmwo (Denosumab-Celtrion)",
                    "preference": "Non-Preferred",
                    "requirespriorauth": "Yes",
                },
            ],
        }
        reference = reference_answer(case)
        self.assertIn("Osenvelt", reference)
        self.assertIn("Denosumab-Celtrion", reference)

        metrics = deterministic_generation_metrics(
            "Osenvelt is Non-Preferred and requires prior authorization. Also Q5158.",
            case,
        )
        self.assertLess(metrics["expected_value_coverage"], 1.0)
        self.assertEqual(metrics["unexpected_codes"], ["Q5158"])
        self.assertFalse(metrics["deterministic_pass"])


if __name__ == "__main__":
    unittest.main()
