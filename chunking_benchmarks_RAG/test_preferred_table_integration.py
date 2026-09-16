"""Compare LangChain Preferred-table results with all 17 source CSV files.

Run with GEHA_RUN_DB_TESTS=1 after starting and loading the pgvector database.
"""

from __future__ import annotations

import csv
import os
import re
import unittest
from pathlib import Path

from chunking_benchmarks_RAG.preferred_table_tool import search_preferred_policy_tables


POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def preferred_names_in_csv(path: Path) -> set[str]:
    """Read explicit Preferred rows independently of the LangChain tool parser."""
    names: set[str] = set()
    preference_index = None
    name_index = None
    blank_rows = 0
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream):
            if not row or not any(cell.strip() for cell in row):
                blank_rows += 1
                if blank_rows >= 2:
                    preference_index = name_index = None
                continue
            blank_rows = 0
            headers = [_key(cell) for cell in row]
            name_header = next(
                (name for name in ("drugname", "name") if name in headers), None
            )
            if "preference" in headers and name_header:
                preference_index = headers.index("preference")
                name_index = headers.index(name_header)
                continue
            if preference_index is None or name_index is None:
                continue
            if max(preference_index, name_index) >= len(row):
                continue
            if _key(row[preference_index]) == "preferred":
                names.add(row[name_index].strip())
    return names


@unittest.skipUnless(
    os.getenv("GEHA_RUN_DB_TESTS") == "1",
    "Set GEHA_RUN_DB_TESTS=1 to run against the loaded pgvector database",
)
class PreferredTableIntegrationTests(unittest.TestCase):
    def test_all_17_preferred_policy_files(self):
        expected = {}
        for csv_path in sorted(POLICY_DIR.glob("geha-coverage-policy-*_table_openai.csv")):
            names = preferred_names_in_csv(csv_path)
            if names:
                source_pdf = csv_path.name.removesuffix("_table_openai.csv") + ".pdf"
                self.assertTrue((POLICY_DIR / source_pdf).is_file(), source_pdf)
                expected[source_pdf] = names
        self.assertEqual(len(expected), 17, "The versioned CSV fixture has changed")

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
                self.assertTrue(all(table["full_table_csv"] for table in result["tables"]))


if __name__ == "__main__":
    unittest.main()
