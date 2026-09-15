import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from chunking_benchmarks_RAG.medical_claims_advisor import (
    build_policy_summary,
    condition_status,
    condition_table_priority,
    evidence_records,
    format_condition_inventory,
    generate_openai_section,
    format_retrieval_summary,
    inventory_evidence,
    is_condition_inventory_query,
    is_preferred_condition_query,
    match_approved_condition_alias,
    preferred_products,
    query_mentions_policy_source,
    query_mentions_condition,
    table_records,
)
from chunking_benchmarks_RAG.table_rag import OPENAI_ASK_INSTRUCTIONS


def result(*, conditions, indication_context=""):
    return {
        "source": "policy.pdf",
        "table_number": 1,
        "title": "Drug preference and prior authorization",
        "full_csv": "Preference,Drug Name\nPreferred,ExampleDrug\n",
        "conditions_json": conditions,
        "indication_context": indication_context,
        "similarity": 0.81234,
    }


class FakeResponses:
    def __init__(self):
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_text="Corrected result")


class MedicalClaimsAdvisorTests(unittest.TestCase):
    def test_all_secondary_condition_eval_queries_match_approved_aliases(self):
        eval_path = Path(__file__).with_name("secondary_condition_evals.json")
        cases = json.loads(eval_path.read_text(encoding="utf-8"))
        for case in cases:
            with self.subTest(case=case["id"]):
                match = match_approved_condition_alias(case["query"])
                self.assertIsNotNone(match)
                self.assertEqual(match["canonical_condition"], case["expected_condition"])
                self.assertEqual(match["source"], case["source"])

    def test_builds_anemia_policy_summary_from_parent_table(self):
        item = result(
            conditions=[
                "Chemotherapy Induced Anemia",
                "Anemia secondary to Myelodysplastic Syndrome",
            ],
            indication_context=(
                "## Chemotherapy Induced Anemia\n\n"
                "- Concurrent myelosuppressive antineoplastic therapy; AND\n\n"
                "## Anemia secondary to Myelodysplastic Syndrome\n\n- Other criterion"
            ),
        )
        item["source"] = "geha-coverage-policy-erythropoietin-stimulating-agents.pdf"
        item["full_csv"] = (
            "Preference,Requires Prior Auth,Drug Name\n"
            "Preferred,Yes,Retacrit\n"
            "Preferred,Yes,Aranesp\n"
            "Non- Preferred,Yes,Epogen\n"
            "Non- Preferred,Yes,Procrit\n"
        )
        summary = build_policy_summary(
            "Which policies discuss anemia caused by cancer treatment?", [item]
        )
        self.assertIsNotNone(summary)
        self.assertEqual(summary["matched_condition"], "Chemotherapy Induced Anemia")
        self.assertEqual(summary["preferred"], ["Retacrit", "Aranesp"])
        self.assertEqual(summary["non_preferred"], ["Epogen", "Procrit"])
        self.assertEqual(len(summary["prior_auth"]), 4)
        self.assertEqual(len(summary["tables"]), 1)
        self.assertEqual(summary["tables"][0]["full_csv"], item["full_csv"])
        self.assertEqual(
            summary["criteria"], ["Concurrent myelosuppressive antineoplastic therapy; AND"]
        )

    def test_matches_multiple_myeloma_by_name_or_mm_abbreviation(self):
        condition = "Multiple Myeloma (MM)"
        self.assertTrue(query_mentions_condition("Show tables for MM", condition))
        self.assertTrue(
            query_mentions_condition("What treats multiple myeloma?", condition)
        )
        self.assertFalse(query_mentions_condition("Show MDS tables", condition))

    def test_matches_policy_identifier_from_source_filename(self):
        source = "geha-coverage-policy-talvey.pdf"
        self.assertTrue(
            query_mentions_policy_source(
                "Which policy applies to Multiple Myeloma for Talvey?", source
            )
        )
        self.assertFalse(
            query_mentions_policy_source(
                "Which policy applies to Multiple Myeloma for Tecvayli?", source
            )
        )

    def test_condition_tables_rank_billing_before_revision_history(self):
        billing = {"title": "Billing codes", "source": "a.pdf", "table_number": 1}
        revision = {
            "title": "Revision history",
            "source": "a.pdf",
            "table_number": 2,
        }
        self.assertLess(condition_table_priority(billing), condition_table_priority(revision))

    def test_detects_corpus_wide_condition_questions(self):
        self.assertTrue(is_condition_inventory_query("List all conditions"))
        self.assertTrue(is_condition_inventory_query("list conditions with policies"))
        self.assertTrue(is_condition_inventory_query("Which conditions have policies?"))
        self.assertTrue(
            is_condition_inventory_query(
                "List all conditions we have preferred treatments for"
            )
        )
        self.assertTrue(is_condition_inventory_query("Show covered conditions"))
        self.assertTrue(
            is_condition_inventory_query("Which conditions have preferred policies?")
        )
        self.assertFalse(is_condition_inventory_query("What condition treats Ziihera?"))

    def test_covered_and_preferred_condition_queries_use_seven_item_inventory(self):
        self.assertTrue(is_preferred_condition_query("Show covered conditions"))
        self.assertTrue(
            is_preferred_condition_query("conditions with preferred policies")
        )
        self.assertFalse(is_preferred_condition_query("List all conditions"))

    def test_extracts_only_exact_preferred_rows(self):
        table = (
            "Preference,Drug Name\n"
            "Preferred,Drug A\n"
            "Non-Preferred,Drug B\n"
            "PREFERRED,Drug C\n"
        )
        self.assertEqual(preferred_products(table), ["Drug A", "Drug C"])

    def test_formats_preferred_condition_inventory_without_llm(self):
        inventory = [
            {
                "condition": "Condition A",
                "preferred_treatments": ["Drug A"],
                "source": "policy-a.pdf",
                "preference_tables": ["Drug preference"],
            },
            {
                "condition": "Condition B",
                "preferred_treatments": [],
                "source": "policy-b.pdf",
                "preference_tables": [],
            },
        ]
        answer = format_condition_inventory(inventory, preferred_only=True)
        self.assertIn("Condition A", answer)
        self.assertIn("Drug A", answer)
        self.assertNotIn("Condition B", answer)
        self.assertIn("policy-level associations", answer)
        self.assertIn("extracted condition metadata", answer)

    def test_explicit_conditions_are_labeled_and_serialized(self):
        item = result(
            conditions=["Biliary Tract Cancer (BTC)"],
            indication_context="## Biliary Tract Cancer (BTC)",
        )
        self.assertEqual(condition_status(item), "EXPLICIT")
        answer = format_retrieval_summary("What is preferred?", [item])
        self.assertIn("Biliary Tract Cancer (BTC)", answer)
        self.assertIn("ExampleDrug", answer)

    def test_missing_conditions_are_unknown_not_excluded(self):
        item = result(conditions=[])
        self.assertEqual(condition_status(item), "NOT_EXPLICITLY_ENUMERATED")
        answer = format_retrieval_summary("What is preferred?", [item])
        self.assertIn("not explicitly enumerated", answer)
        self.assertIn("no condition is inferred", answer)

    def test_evidence_records_are_safe_and_serializable(self):
        records = evidence_records([result(conditions=[])])
        self.assertEqual(records[0]["similarity"], 0.8123)
        self.assertEqual(records[0]["conditions"], [])

    def test_table_records_skips_leading_extraction_artifact(self):
        records = table_records(
            "0,1,2\nPreference,Drug Name,Requires Prior Auth\n"
            "Preferred,Drug A,Yes\n"
        )
        self.assertEqual(records[0]["Drug Name"], "Drug A")

    def test_prior_auth_summary_is_deterministic(self):
        item = result(conditions=["Condition A"])
        item["full_csv"] = (
            "Preference,Drug Name,Requires Prior Auth\n"
            "Preferred,ExampleDrug,Yes\n"
        )
        answer = format_retrieval_summary(
            "Does ExampleDrug require prior authorization?", [item]
        )
        self.assertIn("ExampleDrug: Yes", answer)
        self.assertIn("deterministic rendering", answer)

    def test_openai_ask_is_labeled_and_limited_to_typo_correction(self):
        responses = FakeResponses()
        client = SimpleNamespace(responses=responses)
        answer = generate_openai_section(
            "Correct obvious misspellings", [result(conditions=[])], "test-model", client=client
        )
        self.assertIn("OPENAI ASK", answer)
        self.assertIn("TYPO-CORRECTED", answer)
        self.assertIn("Not GEHA source data", answer)
        self.assertEqual(responses.request["instructions"], OPENAI_ASK_INSTRUCTIONS)
        self.assertFalse(responses.request["store"])
        self.assertIn("Do not add or remove rows", OPENAI_ASK_INSTRUCTIONS)

    def test_inventory_is_passed_to_openai_as_read_only_table_evidence(self):
        evidence = inventory_evidence(
            [
                {
                    "condition": "Condition A",
                    "preferred_treatments": ["Drug A"],
                    "source": "policy-a.pdf",
                }
            ]
        )
        self.assertIn("Condition A", evidence[0]["full_csv"])
        self.assertIn("Drug A", evidence[0]["full_csv"])
        self.assertIn("policy-a.pdf", evidence[0]["full_csv"])

    def test_empty_retrieval_reports_insufficient_geha_evidence(self):
        answer = format_retrieval_summary("question", [])
        self.assertIn("GEHA evidence is insufficient", answer)


if __name__ == "__main__":
    unittest.main()
