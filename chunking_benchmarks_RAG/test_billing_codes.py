import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chunking_benchmarks_RAG.billing_code_data import (
    code_tokens,
    docling_billing_rows,
    requested_billing_codes,
)
from chunking_benchmarks_RAG.generate_billing_code_evals import generate
from chunking_benchmarks_RAG.medical_claims_advisor import (
    format_billing_code_matches,
    retrieve_billing_code_matches,
)


ROOT = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params):
        assert "FROM policy_billing_codes" in statement
        assert params == (sorted(params[0]),)
        return SimpleNamespace(fetchall=lambda: [
            {
                "source_pdf": "geha-coverage-policy-bendamustine.pdf",
                "table_name": "Billing codes",
                "code": "J9033",
                "item_name": "Treanda",
                "source_line": 82,
            },
        ] if "J9033" in params[0] else [])


class BillingCodeTests(unittest.TestCase):
    def test_exact_query_codes_do_not_capture_clinical_counts(self):
        self.assertEqual(requested_billing_codes("Which drug has HCPCS J9033?"), ["J9033"])
        self.assertEqual(requested_billing_codes("What is CPT code 64628?"), ["64628"])
        self.assertEqual(requested_billing_codes("platelet count less than 50000"), [])
        self.assertEqual(code_tokens("J0881 (non-ESRD)"), ["J0881"])

    def test_docling_billing_rows_exclude_preference_and_revision_mentions(self):
        rows = docling_billing_rows(ROOT / "geha-coverage-policy-bendamustine.docling.md")
        self.assertEqual([row["code"] for row in rows], ["J9033", "J9034", "J9036", "J9056", "J9999"])
        self.assertTrue(all(row["table_name"] == "Billing codes" for row in rows))

    def test_fixture_covers_top_level_docling_sources(self):
        fixture_path = Path(__file__).with_name("billing_code_evals.json")
        self.assertEqual(json.loads(fixture_path.read_text(encoding="utf-8")), generate())

    def test_exact_code_lookup_ignores_unrelated_policy_and_preference_duplicate(self):
        with patch("chunking_benchmarks_RAG.medical_claims_advisor.connect", return_value=FakeConnection()):
            matches = retrieve_billing_code_matches("J9033", "unused")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source_document"], "geha-coverage-policy-bendamustine.pdf")
        self.assertEqual(matches[0]["table_name"], "Billing codes")
        self.assertEqual(
            format_billing_code_matches("J9033", matches),
            "- Billing Code: J9033; Source document: geha-coverage-policy-bendamustine.pdf; Table: Billing codes",
        )

    def test_unknown_code_has_no_semantic_fallback(self):
        with patch("chunking_benchmarks_RAG.medical_claims_advisor.connect", return_value=FakeConnection()):
            matches = retrieve_billing_code_matches("J0000", "unused")
        self.assertEqual(matches, [])
        self.assertIn("no exact match", format_billing_code_matches("J0000", matches))


if __name__ == "__main__":
    unittest.main()
