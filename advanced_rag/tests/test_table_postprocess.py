from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from aws_data_workflow.table_postprocess import (
    normalize_markdown_tables,
    postprocess_document,
)


class TablePostprocessTests(unittest.TestCase):
    def test_inherits_headers_for_adjacent_continuation(self) -> None:
        markdown = "| 0 | 1 |\n|---|---|\n| Dental | Covered |\n"
        normalized, headers, findings = normalize_markdown_tables(
            markdown, ["Benefit", "Coverage"]
        )
        self.assertIn("| Benefit | Coverage |", normalized)
        self.assertEqual(headers, ["Benefit", "Coverage"])
        self.assertEqual(findings[0]["method"], "inherited_previous_table")

    def test_two_column_headerless_table_gets_semantic_schema(self) -> None:
        markdown = "| 0 | 1 |\n|---|---|\n| Apply online | kynect.ky.gov |\n"
        normalized, _, findings = normalize_markdown_tables(markdown)
        self.assertIn("| Field | Details |", normalized)
        self.assertEqual(findings[0]["method"], "two_column_key_value_schema")

    def test_postprocess_preserves_raw_and_writes_normalized_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document = Path(temporary) / "doc-test"
            page = document / "pages" / "page-001"
            page.mkdir(parents=True)
            raw = "| 0 | 1 |\n|---|---|\n| Name | Value |\n"
            (page / "docling.md").write_text(raw, encoding="utf-8")
            table = document / "visuals" / "tables" / "table-001"
            table.mkdir(parents=True)
            with (table / "table.csv").open(
                "w", newline="", encoding="utf-8"
            ) as stream:
                csv.writer(stream).writerows([["0", "1"], ["Name", "Value"]])
            (table / "metadata.json").write_text(
                json.dumps({
                    "provenance": [{"page_no": 1}],
                    "artifacts": {},
                    "issues": [],
                }),
                encoding="utf-8",
            )

            report = postprocess_document(document)

            self.assertEqual((page / "docling.md").read_text(encoding="utf-8"), raw)
            self.assertTrue((page / "docling.normalized.md").is_file())
            self.assertTrue((table / "table.normalized.csv").is_file())
            self.assertEqual(report["normalized"], 2)
