"""Policy MCP adapter tests; no database, model download, or external calls."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from policy_service import PolicyService


TABLE = {
    "source": "geha-coverage-policy-bendamustine.pdf",
    "table_number": 1,
    "title": "Drug preference and prior authorization",
    "full_csv": "Drug Name,Preference\nTreanda,Preferred\n",
    "conditions_json": ["Cancer"],
    "similarity": 0.91347,
}


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, _sql, params):
        self.params = params
        return self

    def fetchone(self):
        return TABLE


class PolicyServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = PolicyService("postgresql://test", "fake-embedding")
        self.billing = SimpleNamespace(requested_billing_codes=Mock(return_value=[]))
        self.advisor = SimpleNamespace(
            retrieve_billing_code_matches=Mock(return_value=[]),
            retrieve_tables_for_named_condition=Mock(return_value=[TABLE]),
            retrieve_claims_evidence=Mock(return_value=[TABLE]),
            retrieve_policy_sections=Mock(return_value=[
                {"chunk_number": 2, "section_type": "indication", "content": "Criteria"}
            ]),
            is_revision_table=lambda title: "revision" in title.casefold(),
        )
        self.connection = FakeConnection()
        self.rag = SimpleNamespace(connect=Mock(return_value=self.connection))
        backend = patch("policy_service._backend", return_value=(
            self.billing, self.advisor, self.rag
        ))
        backend.start()
        self.addCleanup(backend.stop)

    def test_named_lookup_returns_citation_without_full_table(self):
        result = self.service.search("bendamustine")
        self.assertEqual(result["route"], "policy_or_condition")
        self.assertEqual(result["tables"][0]["source_pdf"], TABLE["source"])
        self.assertEqual(result["tables"][0]["similarity"], 0.9135)
        self.assertNotIn("full_csv", result["tables"][0])
        self.advisor.retrieve_claims_evidence.assert_not_called()

    def test_exact_code_never_runs_semantic_search(self):
        self.billing.requested_billing_codes.return_value = ["J9033"]
        self.advisor.retrieve_billing_code_matches.return_value = [{
            "billing_code": "J9033", "source_document": TABLE["source"]
        }]
        result = self.service.search("billing code J9033")
        self.assertEqual(result["route"], "exact_billing_code")
        self.assertEqual(result["match_count"], 1)
        self.advisor.retrieve_tables_for_named_condition.assert_not_called()
        self.advisor.retrieve_claims_evidence.assert_not_called()

    def test_semantic_fallback_only_when_direct_lookup_empty(self):
        self.advisor.retrieve_tables_for_named_condition.return_value = []
        with patch("policy_service._embedding_model", return_value="embedding"):
            result = self.service.search("injectable treatment", top_tables=2)
        self.assertEqual(result["route"], "semantic_fallback")
        self.advisor.retrieve_claims_evidence.assert_called_once_with(
            "injectable treatment",
            database_url="postgresql://test",
            embedding_model="embedding",
            top_tables=2,
            candidate_rows=30,
        )

    def test_get_evidence_returns_complete_table_and_criteria(self):
        result = self.service.evidence(TABLE["source"], 1, "Cancer")
        self.assertEqual(result["table_csv"], TABLE["full_csv"])
        self.assertEqual(result["criteria_sections"][0]["content"], "Criteria")
        self.assertEqual(self.connection.params, (TABLE["source"], 1))

    def test_rejects_bad_queries_and_source_paths(self):
        for query in ("", " " * 5, "x" * 501, "bad\x00input"):
            with self.subTest(query=query[:20]), self.assertRaises(ValueError):
                self.service.search(query)
        with self.assertRaises(ValueError):
            self.service.search("okay", top_tables=9)
        for source in ("../secret.pdf", "/tmp/secret.pdf", "a.txt"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.service.evidence(source, 1)


if __name__ == "__main__":
    unittest.main()
