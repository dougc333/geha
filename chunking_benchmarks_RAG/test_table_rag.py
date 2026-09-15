import json
import tempfile
import unittest
from pathlib import Path

from chunking_benchmarks_RAG.table_rag import (
    extract_indication_metadata,
    infer_title,
    normalized_table,
    row_search_text,
    split_csv_tables,
)


class TableRagTests(unittest.TestCase):
    def test_pdf_verified_indication_specific_criteria_evals(self):
        project_root = Path(__file__).resolve().parents[1]
        eval_path = Path(__file__).with_name(
            "indication_specific_criteria_evals.json"
        )
        cases = json.loads(eval_path.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 26)

        for case in cases:
            with self.subTest(case=case["id"]):
                markdown_path = (
                    project_root
                    / "downloads"
                    / "coverage-policies"
                    / case["source"].replace(".pdf", ".docling.md")
                )
                conditions, _ = extract_indication_metadata(markdown_path)
                self.assertIn(case["expected_condition"], conditions)

    def test_two_blank_rows_separate_tables(self):
        content = "a,b\n1,2\n\n\nc,d\n3,4\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tables.csv"
            path.write_text(content, encoding="utf-8")
            tables = split_csv_tables(path)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0], [["a", "b"], ["1", "2"]])
        self.assertEqual(tables[1], [["c", "d"], ["3", "4"]])

    def test_normalizes_short_rows(self):
        headers, rows = normalized_table([["a", "b"], ["1"]])
        self.assertEqual(headers, ["a", "b"])
        self.assertEqual(rows, [["1", ""]])

    def test_discards_dataframe_index_header_artifact(self):
        headers, rows = normalized_table(
            [
                ["0", "1", "2"],
                ["Drug Name", "HCPCS Code", "Description"],
                ["Ziihera", "J9276", "Injection"],
            ]
        )
        self.assertEqual(headers, ["Drug Name", "HCPCS Code", "Description"])
        self.assertEqual(rows, [["Ziihera", "J9276", "Injection"]])

    def test_infers_billing_title(self):
        self.assertEqual(
            infer_title(["Drug Name", "HCPCS Code", "Description"]),
            "Billing codes",
        )

    def test_extracts_single_indication_and_context(self):
        markdown = """## Drug
## Indication Specific Criteria:
## Biliary Tract Cancer (BTC)

- Supporting criterion
## Universal Approval Criteria:
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.docling.md"
            path.write_text(markdown, encoding="utf-8")
            conditions, context = extract_indication_metadata(path)
        self.assertEqual(conditions, ["Biliary Tract Cancer (BTC)"])
        self.assertIn("Supporting criterion", context)
        self.assertNotIn("Universal Approval Criteria", context)

    def test_extracts_inline_and_multiline_indications(self):
        markdown = """## Indication Specific Criteria Breast cancer - unresectable or metastatic
## EGFR-Mutated Non-squamous non-small cell lung cancer -
## locally advanced or metastatic
## Universal Approval Criteria:
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.docling.md"
            path.write_text(markdown, encoding="utf-8")
            conditions, _ = extract_indication_metadata(path)
        self.assertEqual(
            conditions,
            [
                "Breast cancer - unresectable or metastatic",
                "EGFR-Mutated Non-squamous non-small cell lung cancer - locally advanced or metastatic",
            ],
        )

    def test_missing_indication_section_is_explicitly_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.docling.md"
            path.write_text("## Universal Approval Criteria:\n", encoding="utf-8")
            self.assertEqual(extract_indication_metadata(path), ([], ""))

    def test_conditions_are_embedded_with_each_table_row(self):
        text = row_search_text(
            "policy.pdf",
            "Drug preference",
            ["Drug Name"],
            ["Ziihera"],
            ["Biliary Tract Cancer (BTC)"],
        )
        self.assertIn("Conditions: Biliary Tract Cancer (BTC)", text)


if __name__ == "__main__":
    unittest.main()
