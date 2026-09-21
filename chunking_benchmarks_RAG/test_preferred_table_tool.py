"""Tests for the LangChain Preferred-table lookup tool."""

import unittest
from unittest.mock import patch

from chunking_benchmarks_RAG.preferred_table_tool import (
    find_preferred_policy_tables,
    search_preferred_policy_tables,
)


class PreferredTableToolTests(unittest.TestCase):
    @patch("chunking_benchmarks_RAG.preferred_table_tool.retrieve_tables_for_named_condition")
    def test_returns_only_preferred_tables_with_full_evidence(self, retrieve):
        retrieve.return_value = [
            {
                "source": "geha-coverage-policy-bendamustine.pdf",
                "table_number": 1,
                "title": "Drug preference and prior authorization",
                "full_html": "<table><tr><td>Preferred</td><td>Treanda</td></tr><tr><td>Non-preferred</td><td>Bendeka</td></tr></table>",
                "rows_json": [
                    {"Preference": "Preferred", "Drug Name": "Treanda"},
                    {"Preference": "Non-preferred", "Drug Name": "Bendeka"},
                ],
                "conditions_json": ["Follicular lymphoma"],
            },
            {
                "source": "geha-coverage-policy-bendamustine.pdf",
                "table_number": 2,
                "title": "Billing codes",
                "full_html": "<table><tr><td>Treanda</td><td>J9033</td></tr></table>",
                "rows_json": [{"Drug Name": "Treanda", "HCPCS Code": "J9033"}],
                "conditions_json": [],
            },
            {
                "source": "geha-coverage-policy-bendamustine.pdf",
                "table_number": 3,
                "title": "Revision history",
                "full_html": "<table><tr><td>Preferred</td><td>OldValue</td></tr></table>",
                "rows_json": [{"Preference": "Preferred", "Drug Name": "OldValue"}],
                "conditions_json": [],
            },
        ]

        result = find_preferred_policy_tables(" bendamustine ", "postgresql://test")

        retrieve.assert_called_once_with("bendamustine", "postgresql://test")
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["tables"][0]["preferred_products"], ["Treanda"])
        self.assertEqual(
            result["tables"][0]["explicit_conditions"], ["Follicular lymphoma"]
        )
        self.assertIn("Non-preferred", result["tables"][0]["full_table_html"])
        self.assertEqual(len(result["tables"][0]["rows"]), 2)

    @patch("chunking_benchmarks_RAG.preferred_table_tool.retrieve_tables_for_named_condition")
    def test_no_preferred_row_is_not_a_coverage_decision(self, retrieve):
        retrieve.return_value = [{
            "source": "geha-coverage-policy-nplate.pdf",
            "table_number": 1,
            "title": "Billing codes",
            "full_html": "<table><tr><td>Nplate</td><td>J2802</td></tr></table>",
            "rows_json": [{"Drug Name": "Nplate", "HCPCS Code": "J2802"}],
            "conditions_json": [],
        }]

        result = find_preferred_policy_tables("nplate", "postgresql://test")

        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["tables"], [])
        self.assertIn("does not establish", result["note"])

    def test_langchain_tool_has_string_query_input(self):
        self.assertEqual(search_preferred_policy_tables.name, "search_preferred_policy_tables")
        self.assertIn("query", search_preferred_policy_tables.args)
        self.assertEqual(search_preferred_policy_tables.args["query"]["type"], "string")

    def test_blank_query_rejected(self):
        with self.assertRaisesRegex(ValueError, "query must name"):
            find_preferred_policy_tables("  ", "postgresql://test")


if __name__ == "__main__":
    unittest.main()
