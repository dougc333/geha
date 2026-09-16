import json
import tempfile
import unittest
from pathlib import Path

from chunking_benchmarks_RAG.table_rag import (
    classify_policy_chunks,
    extract_indication_metadata,
    infer_title,
    normalized_table,
    policy_chunk_paths,
    policy_source_terms,
    row_search_text,
    split_csv_tables,
    split_markdown_chunks,
)


class TableRagTests(unittest.TestCase):
    def test_policy_chunk_ingestion_ignores_subdirectories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            top_level = root / "geha-coverage-policy-nplate.docling_chunks.md"
            top_level.write_text("## Chunk 1\nNplate", encoding="utf-8")
            nested = root / "aa_source_not_consistent"
            nested.mkdir()
            (nested / "geha-medical-necessity-review-criteria.docling_chunks.md").write_text(
                "## Chunk 1\nRevision history", encoding="utf-8"
            )
            self.assertEqual(policy_chunk_paths(root), [top_level])

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

    def test_nplate_chunks_are_separate_indications_and_universal_criteria(self):
        root = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
        chunks_path = root / "geha-coverage-policy-nplate.docling_chunks.md"
        conditions, _ = extract_indication_metadata(
            root / "geha-coverage-policy-nplate.docling.md"
        )
        chunks = split_markdown_chunks(chunks_path)
        labeled = classify_policy_chunks(chunks, conditions)
        self.assertEqual(
            [(item["chunk_number"], item["condition"]) for item in labeled
             if item["section_type"] == "indication"],
            [
                (2, "Chemotherapy-induced thrombocytopenia"),
                (3, "Myelodysplastic Syndrome"),
            ],
        )
        self.assertEqual(labeled[3]["section_type"], "universal")
        self.assertEqual(labeled[6]["section_type"], "disclaimer")
        terms = policy_source_terms(
            "geha-coverage-policy-nplate.pdf",
            chunks,
            root / "geha-coverage-policy-nplate_table_openai.csv",
            conditions,
        )
        self.assertIn("nplate", terms)
        self.assertIn("romiplostim", terms)

    def test_every_documented_indication_is_labeled_in_chunk_corpus(self):
        root = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
        paths = sorted(root.rglob("*.docling_chunks.md"))
        self.assertEqual(len(paths), 35)
        for path in paths:
            with self.subTest(path=path.name):
                markdown = path.with_name(
                    path.name.replace(".docling_chunks.md", ".docling.md")
                )
                expected, _ = extract_indication_metadata(markdown)
                labeled = classify_policy_chunks(split_markdown_chunks(path), expected)
                found = {
                    item["condition"] for item in labeled
                    if item["section_type"] == "indication"
                }
                self.assertEqual(set(expected) - found, set())

    def test_filename_eval_manifest_covers_every_root_policy_chunk_file(self):
        root = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
        manifest = json.loads(
            Path(__file__).with_name("policy_name_section_evals.json").read_text(
                encoding="utf-8"
            )
        )
        root_sources = {
            path.name.replace(".docling_chunks.md", ".pdf")
            for path in root.glob("*.docling_chunks.md")
        }
        case_sources = {case["source"] for case in manifest["cases"]}
        self.assertEqual(len(manifest["cases"]), 34)
        self.assertEqual(case_sources, root_sources)
        nested = manifest["stored_only"]["source"]
        self.assertEqual(
            nested,
            "aa_source_not_consistent/geha-medical-necessity-review-criteria.pdf",
        )
        self.assertTrue((root / nested.replace(".pdf", ".docling_chunks.md")).exists())


if __name__ == "__main__":
    unittest.main()
