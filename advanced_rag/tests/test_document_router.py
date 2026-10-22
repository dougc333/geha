from __future__ import annotations

import unittest

from aws_data_workflow.document_router import classify_document


class DocumentRouterTests(unittest.TestCase):
    def test_detects_coverage_policy(self) -> None:
        result = classify_document(
            "geha-coverage-policy-bendamustine.pdf",
            "Medical necessity and prior authorization requirements apply.",
        )
        self.assertTrue(result["is_policy"])
        self.assertEqual(result["document_type"], "coverage_policy")
        self.assertEqual(result["route"], "policy_rag")

    def test_detects_plan_brochure(self) -> None:
        result = classify_document(
            "2026-dental-plan-brochure.pdf",
            "This brochure is the official statement of benefits.",
        )
        self.assertTrue(result["is_policy"])
        self.assertEqual(result["document_type"], "benefit_plan")

    def test_routes_invoice_away_from_policy_rag(self) -> None:
        result = classify_document(
            "medical-invoice.pdf",
            "Invoice number 123. Amount due $75.00.",
        )
        self.assertFalse(result["is_policy"])
        self.assertEqual(result["route"], "generic_artifacts")

    def test_ambiguous_single_term_does_not_trigger_policy_route(self) -> None:
        result = classify_document(
            "meeting-notes.pdf",
            "The team discussed benefits during the meeting.",
        )
        self.assertFalse(result["is_policy"])

    def test_routes_health_coverage_application_as_whole_document(self) -> None:
        result = classify_document(
            "Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf",
            "Application for One Person. Use this application to see what insurance choices you qualify for.",
        )
        self.assertTrue(result["is_form_application"])
        self.assertEqual(result["document_type"], "form_application")
        self.assertEqual(result["route"], "whole_document_context")

    def test_provider_directory_is_not_a_form(self) -> None:
        result = classify_document(
            "optical_providers_adult_medicaid.pdf",
            "Active Optical Providers. Provider name, address, city, state, ZIP and phone.",
        )
        self.assertFalse(result["is_form_application"])
        self.assertEqual(result["route"], "generic_artifacts")


if __name__ == "__main__":
    unittest.main()

