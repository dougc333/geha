"""Deterministic signup flow and telemetry redaction tests."""

import unittest

from support import ROOT  # also configures query/ on sys.path

from signup.graph import is_benefit_question, transition
from signup.redaction import sanitize
from signup.service import process_turn


def application(stage="eligibility", slots=None):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "member_ref": "opaque-subject",
        "product": "dental",
        "coverage_year": 2026,
        "stage": stage,
        "status": "active",
        "slots": slots or {},
        "version": 0,
    }


class SignupGraphTest(unittest.TestCase):
    def test_happy_path_is_deterministic(self):
        result = transition("eligibility", "active", {}, "yes")
        self.assertEqual(result.stage, "household")
        result = transition(result.stage, result.status, result.slots, "Self Plus One")
        self.assertEqual(result.stage, "plan_selection")
        result = transition(result.stage, result.status, result.slots, "High")
        self.assertEqual(result.stage, "contact")
        result = transition(result.stage, result.status, result.slots, "98101 me@example.com")
        self.assertEqual(result.stage, "review")
        result = transition(result.stage, result.status, result.slots, "confirm")
        self.assertEqual((result.stage, result.status), ("completed", "completed"))

    def test_ineligible_member_goes_to_handoff(self):
        result = transition("eligibility", "active", {}, "No, I am not eligible")
        self.assertEqual((result.stage, result.status, result.event), ("handoff", "handoff", "handoff"))

    def test_benefit_question_does_not_advance_state(self):
        self.assertTrue(is_benefit_question("Does High cover root canals?"))
        result = transition("plan_selection", "active", {"eligible": True},
                            "Does High cover root canals?")
        self.assertTrue(result.benefit_question)
        self.assertEqual(result.stage, "plan_selection")


class SignupServiceTest(unittest.TestCase):
    def test_rag_answer_resumes_same_signup_prompt(self):
        calls = []

        def answer(question, document_ids):
            calls.append((question, document_ids))
            return "High covers major services at the documented rate [1].", [{"n": 1}]

        app = application("plan_selection", {"eligible": True, "coverage_type": "self_only"})
        response = process_turn(app, "How does High cover crowns?", {}, ["dental-2026"], answer)
        self.assertEqual(response["application"]["stage"], "plan_selection")
        self.assertIn("To continue signup", response["reply"])
        self.assertEqual(response["sources"], [{"n": 1}])
        self.assertEqual(calls[0][1], ["dental-2026"])


class RedactionTest(unittest.TestCase):
    def test_sensitive_fields_and_free_text_are_redacted(self):
        value = sanitize({
            "email": "member@example.com",
            "message": "Email member@example.com or call 202-555-0182; SSN 123-45-6789",
            "stage": "contact",
        })
        self.assertEqual(value["email"], "[REDACTED]")
        self.assertNotIn("member@example.com", value["message"])
        self.assertNotIn("202-555-0182", value["message"])
        self.assertNotIn("123-45-6789", value["message"])
        self.assertEqual(value["stage"], "contact")


if __name__ == "__main__":
    unittest.main()
