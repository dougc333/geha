"""Compare LangChain Preferred-table results with all reviewed HTML tables.

Run with GEHA_RUN_DB_TESTS=1 after starting and loading the pgvector database.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

from chunking_benchmarks_RAG.html_table_data import load_policy_html_tables
from chunking_benchmarks_RAG.preferred_table_tool import search_preferred_policy_tables

POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def preferred_names_in_table(table: dict) -> set[str]:
    """Read explicit Preferred rows independently of the LangChain tool parser."""
    names: set[str] = set()
    for record in table["rows_json"]:
        row = {_key(key): str(value) for key, value in record.items()}
        if _key(row.get("preference", "")) == "preferred":
            name = row.get("drugname") or row.get("name")
            if name:
                names.add(name.strip())
    return names


@unittest.skipUnless(
    os.getenv("GEHA_RUN_DB_TESTS") == "1",
    "Set GEHA_RUN_DB_TESTS=1 to run against the loaded pgvector database",
)
class PreferredTableIntegrationTests(unittest.TestCase):
    def test_all_17_preferred_policy_files(self):
        expected = {}
        for table in load_policy_html_tables(POLICY_DIR):
            names = preferred_names_in_table(table)
            if names:
                source_pdf = table["source"]
                self.assertTrue((POLICY_DIR / source_pdf).is_file(), source_pdf)
                expected.setdefault(source_pdf, set()).update(names)
        self.assertEqual(len(expected), 17, "The reviewed HTML fixture has changed")

        for source_pdf, names in expected.items():
            with self.subTest(source_pdf=source_pdf):
                query = source_pdf.removeprefix("geha-coverage-policy-").removesuffix(".pdf")
                query = query.replace("-", " ")
                result = search_preferred_policy_tables.invoke({"query": query})
                self.assertGreater(result["match_count"], 0)
                self.assertEqual(result["match_count"], len(result["tables"]))
                self.assertEqual(
                    {table["source_pdf"] for table in result["tables"]},
                    {source_pdf},
                )
                actual_names = {
                    name
                    for table in result["tables"]
                    for name in table["preferred_products"]
                }
                self.assertEqual(actual_names, names)
                self.assertTrue(all(table["full_table_html"] for table in result["tables"]))


if __name__ == "__main__":
    unittest.main()
