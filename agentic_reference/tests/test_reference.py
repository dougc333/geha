from __future__ import annotations

import unittest

from geha_reference.bootstrap import build_agent
from geha_reference.models import UserContext


class ReferenceAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = build_agent()
        cls.member = UserContext(
            actor_id="member-1000",
            role="member",
            subject_member_ids=frozenset({"Gy001000"}),
        )
        cls.other_member = UserContext(
            actor_id="member-other",
            role="member",
            subject_member_ids=frozenset({"not-the-owner"}),
        )

    def test_authorized_member_can_get_claim_status(self):
        response = self.agent.run("Status of CLM-100000", self.member)
        self.assertEqual(response.intent, "claim_status")
        self.assertIn("CLM-100000", response.answer)
        self.assertEqual(response.structured_data["claim_id"], "CLM-100000")
        self.assertIsNotNone(response.audit_id)

    def test_impossible_claim_timeline_is_flagged(self):
        response = self.agent.run("Status of CLM-100000", self.member)
        self.assertTrue(response.needs_human_review)
        self.assertIn(
            "received_before_submitted",
            response.structured_data["data_quality_flags"],
        )
        self.assertIn("Verify it in the system of record", response.answer)

    def test_cross_member_claim_access_is_denied(self):
        response = self.agent.run("Status of CLM-100000", self.other_member)
        self.assertEqual(
            response.answer,
            "The claim was not found or you are not authorized to view it.",
        )
        self.assertEqual(response.structured_data, {})

    def test_submission_guidance_is_cited(self):
        response = self.agent.run(
            "How do I submit an out-of-network claim?",
            self.member,
        )
        self.assertEqual(response.intent, "claim_submission")
        self.assertTrue(response.citations)
        self.assertTrue(any("geha.com" in item.url for item in response.citations))

    def test_appeal_requires_human_review(self):
        response = self.agent.run("Appeal CLM-100000", self.member)
        self.assertEqual(response.intent, "appeal_support")
        self.assertTrue(response.needs_human_review)
        self.assertTrue(response.citations)
        self.assertIn("required_fields", response.structured_data)

    def test_coverage_question_requires_human_review(self):
        response = self.agent.run(
            "Is this service covered and should we approve it?",
            self.member,
        )
        self.assertTrue(response.needs_human_review)

    def test_audit_events_do_not_store_prompt_text(self):
        secret_marker = "synthetic-secret-marker"
        self.agent.run(f"How do I file a claim? {secret_marker}", self.member)
        events = self.agent.tools.audit.events
        self.assertTrue(events)
        self.assertNotIn(secret_marker, repr(events[-1]))


if __name__ == "__main__":
    unittest.main()
