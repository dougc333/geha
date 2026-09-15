import unittest
from types import SimpleNamespace

from chunking_benchmarks_RAG.medical_claims_advisor import (
    ADVISOR_INSTRUCTIONS,
    build_evidence_context,
    condition_status,
    evidence_records,
    generate_claims_advice,
)


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
        return SimpleNamespace(output_text="Grounded answer")


class MedicalClaimsAdvisorTests(unittest.TestCase):
    def test_explicit_conditions_are_labeled_and_serialized(self):
        item = result(
            conditions=["Biliary Tract Cancer (BTC)"],
            indication_context="## Biliary Tract Cancer (BTC)",
        )
        self.assertEqual(condition_status(item), "EXPLICIT")
        context = build_evidence_context([item])
        self.assertIn('CONDITIONS: ["Biliary Tract Cancer (BTC)"]', context)
        self.assertIn("## Biliary Tract Cancer (BTC)", context)

    def test_missing_conditions_are_unknown_not_excluded(self):
        item = result(conditions=[])
        self.assertEqual(condition_status(item), "NOT_EXPLICITLY_ENUMERATED")
        context = build_evidence_context([item])
        self.assertIn("No explicit Indication Specific Criteria", context)
        self.assertIn("Absence of a condition is not evidence", ADVISOR_INSTRUCTIONS)

    def test_evidence_records_are_safe_and_serializable(self):
        records = evidence_records([result(conditions=[])])
        self.assertEqual(records[0]["similarity"], 0.8123)
        self.assertEqual(records[0]["conditions"], [])

    def test_llm_receives_question_and_grounded_evidence(self):
        responses = FakeResponses()
        client = SimpleNamespace(responses=responses)
        answer = generate_claims_advice(
            "Does ExampleDrug require prior authorization?",
            [result(conditions=[])],
            "test-model",
            client=client,
        )
        self.assertEqual(answer, "Grounded answer")
        self.assertEqual(responses.request["instructions"], ADVISOR_INSTRUCTIONS)
        self.assertIn("ExampleDrug", responses.request["input"])
        self.assertIn("NOT_EXPLICITLY_ENUMERATED", responses.request["input"])


if __name__ == "__main__":
    unittest.main()

