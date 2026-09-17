import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from chunking_benchmarks_RAG.policy_table_html_lib import (
    extract_pdf,
    inherit_continuation_header,
    looks_like_revision_history,
    native_text_converter,
    ocr_table_converter,
    promote_embedded_header,
    slugify,
    standalone_html,
)


class HtmlTableExtractionTests(unittest.TestCase):
    def test_restores_first_data_row_used_as_next_page_column_names(self):
        previous = pd.DataFrame(
            [["Avastin", "J9035", "Injection"]],
            columns=["Drug Name", "HCPCS Code", "Description"],
        )
        fragment = pd.DataFrame(
            [["Alymsys", "J9400", "Injection"]],
            columns=["Zirabev", "Q5118", "Injection, bevacizumab-bvzr"],
        )
        restored, changed = inherit_continuation_header(
            fragment, previous,
            heading="Billing", previous_heading="Billing",
            page_number=3, previous_page=2,
        )
        self.assertTrue(changed)
        self.assertEqual(list(restored.columns), list(previous.columns))
        self.assertEqual(restored["Drug Name"].tolist(), ["Zirabev", "Alymsys"])
        self.assertEqual(restored["HCPCS Code"].tolist(), ["Q5118", "J9400"])
        self.assertEqual(list(fragment.columns), [
            "Zirabev", "Q5118", "Injection, bevacizumab-bvzr"
        ])

    def test_does_not_restore_unrelated_named_columns(self):
        previous = pd.DataFrame(
            [["Avastin", "J9035", "Injection"]],
            columns=["Drug Name", "HCPCS Code", "Description"],
        )
        fragment = pd.DataFrame(
            [["Some value", "Another value", "Details"]],
            columns=["Condition", "Status", "Notes"],
        )
        unchanged, changed = inherit_continuation_header(
            fragment, previous,
            heading="Billing", previous_heading="Billing",
            page_number=3, previous_page=2,
        )
        self.assertFalse(changed)
        self.assertIs(unchanged, fragment)

    def test_inherits_billing_headers_for_verified_next_page_continuations(self):
        previous = pd.DataFrame(
            [["Avastin", "J9035", "Injection, bevacizumab, 10 mg"]],
            columns=["Drug Name", "HCPCS Code", "Description"],
        )
        fragment = pd.DataFrame(
            [["Vegzelma", "Q5129", "Injection, bevacizumab-adcd, 10 mg"]],
            columns=[0, 1, 2],
        )
        for heading in ("Billing", "Billing Codes"):
            with self.subTest(heading=heading):
                inherited, changed = inherit_continuation_header(
                    fragment, previous,
                    heading=heading, previous_heading=heading,
                    page_number=3, previous_page=2,
                )
                self.assertTrue(changed)
                self.assertEqual(list(inherited.columns), list(previous.columns))
                self.assertEqual(inherited.iloc[0]["HCPCS Code"], "Q5129")
                self.assertEqual(list(fragment.columns), [0, 1, 2])

    def test_does_not_inherit_without_strong_continuation_evidence(self):
        previous = pd.DataFrame(
            [["Avastin", "J9035", "Injection"]],
            columns=["Drug Name", "HCPCS Code", "Description"],
        )
        fragment = pd.DataFrame([["Vegzelma", "Q5129", "Injection"]], columns=[0, 1, 2])
        cases = (
            ("Billing", "Billing", 2, 2),
            ("Other section", "Billing", 3, 2),
            ("Extracted table", "Extracted table", 3, 2),
        )
        for heading, previous_heading, page, previous_page in cases:
            with self.subTest(heading=heading, page=page):
                unchanged, inherited = inherit_continuation_header(
                    fragment, previous,
                    heading=heading, previous_heading=previous_heading,
                    page_number=page, previous_page=previous_page,
                )
                self.assertFalse(inherited)
                self.assertIs(unchanged, fragment)

    def test_html_extractor_inherits_header_without_dropping_continuation_rows(self):
        first = pd.DataFrame(
            [["Avastin", "J9035", "Injection"]],
            columns=["Drug Name", "HCPCS Code", "Description"],
        )
        second = pd.DataFrame(
            [["Vegzelma", "Q5129", "Injection"], ["Avzivi", "J9999", "Description"]],
            columns=[0, 1, 2],
        )
        tables = [
            SimpleNamespace(
                label="table", text="", self_ref=f"#/tables/{index}",
                prov=[SimpleNamespace(page_no=index + 2)],
                export_to_dataframe=lambda doc, frame=frame: frame,
            )
            for index, frame in enumerate((first, second))
        ]
        document = SimpleNamespace(tables=tables)
        converter = SimpleNamespace(convert=lambda pdf: SimpleNamespace(document=document))
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch("chunking_benchmarks_RAG.policy_table_html_lib.require_embedded_text"),
                patch("chunking_benchmarks_RAG.policy_table_html_lib.heading_map", return_value={
                    table.self_ref: "Billing" for table in tables
                }),
            ):
                result = extract_pdf(
                    Path("geha-coverage-policy-bevacizumab.pdf"),
                    Path(directory), converter, converter,
                )
            self.assertEqual(result["tables_written"], 2)
            continuation = result["outputs"][1]
            self.assertEqual(continuation["header_inherited_from_table"], 1)
            self.assertEqual(continuation["rows"], 2)
            rendered = (Path(directory) / continuation["html"]).read_text()
            self.assertIn("<th>Drug Name</th>", rendered)
            self.assertIn("<th>HCPCS Code</th>", rendered)
            self.assertNotIn("<th>0</th>", rendered)
            self.assertIn("Vegzelma", rendered)
            self.assertIn("Avzivi", rendered)

    def test_promotes_known_header_row_from_numeric_columns(self):
        raw = pd.DataFrame(
            [
                ["Drug Name", "HCPCS Code", "Description"],
                ["Treanda", "J9033", "Injection, bendamustine hydrochloride"],
            ],
            columns=[0, 1, 2],
        )
        repaired, promoted = promote_embedded_header(raw)
        self.assertTrue(promoted)
        self.assertEqual(list(repaired.columns), ["Drug Name", "HCPCS Code", "Description"])
        self.assertEqual(repaired.iloc[0]["HCPCS Code"], "J9033")
        self.assertEqual(list(raw.columns), [0, 1, 2])

    def test_numeric_columns_do_not_drop_a_data_row(self):
        raw = pd.DataFrame(
            [["Treanda", "J9033", "Injection"], ["Bendeka", "J9034", "Injection"]],
            columns=[0, 1, 2],
        )
        repaired, promoted = promote_embedded_header(raw)
        self.assertFalse(promoted)
        self.assertIs(repaired, raw)

    def test_html_extractor_uses_promoted_header_and_reports_repair(self):
        raw = pd.DataFrame(
            [["Drug Name", "HCPCS Code", "Description"], ["Treanda", "J9033", "Injection"]],
            columns=[0, 1, 2],
        )
        table = SimpleNamespace(
            label="table",
            text="",
            self_ref="#/tables/0",
            prov=[SimpleNamespace(page_no=2)],
            export_to_dataframe=lambda doc: raw,
        )
        document = SimpleNamespace(
            tables=[table],
            iterate_items=lambda: iter([(table, 0)]),
        )
        converter = SimpleNamespace(convert=lambda pdf: SimpleNamespace(document=document))
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            with patch("chunking_benchmarks_RAG.policy_table_html_lib.require_embedded_text"):
                result = extract_pdf(
                    Path("geha-coverage-policy-bendamustine.pdf"),
                    output_dir,
                    converter,
                    converter,
                )
            self.assertEqual(result["tables_written"], 1)
            self.assertTrue(result["outputs"][0]["header_promoted"])
            self.assertEqual(result["outputs"][0]["rows"], 1)
            rendered = (output_dir / result["outputs"][0]["html"]).read_text()
            self.assertIn("<th>Drug Name</th>", rendered)
            self.assertIn("<th>HCPCS Code</th>", rendered)
            self.assertNotIn("<th>0</th>", rendered)

    def test_detects_clean_revision_table(self):
        frame = pd.DataFrame(
            [["1/1/2026", "Annual Review"]], columns=["!Date", "!Updates"]
        )
        self.assertTrue(looks_like_revision_history(frame, "For Internal Use ONLY"))

    def test_detects_revision_fragment_with_first_row_as_header(self):
        frame = pd.DataFrame(
            [["March 2024", "Updated definition"], ["April 2024", "Added criteria"]],
            columns=["January 2024", "Origination"],
        )
        self.assertTrue(looks_like_revision_history(frame, "For Internal Use ONLY"))

    def test_preserves_clinical_table(self):
        frame = pd.DataFrame(
            [["Preferred", "Treanda", "J9033"]],
            columns=["Preference", "Drug Name", "HCPCS Code"],
        )
        self.assertFalse(looks_like_revision_history(frame, "Bendamustine"))

    def test_slug_is_stable(self):
        self.assertEqual(slugify("Billing / HCPCS Codes"), "billing-hcpcs-codes")

    def test_html_is_standalone_and_escapes_values(self):
        frame = pd.DataFrame([["A&B"]], columns=["Drug <Name>"])
        rendered = standalone_html(
            source="policy.pdf",
            heading="Billing & Codes",
            table_number=1,
            page_number=2,
            frame=frame,
        )
        self.assertIn("<!doctype html>", rendered)
        self.assertIn("<style>", rendered)
        self.assertIn("<table", rendered)
        self.assertIn("Billing &amp; Codes", rendered)
        self.assertIn("A&amp;B", rendered)


class PdfFixtureIntegrationTests(unittest.TestCase):
    """Run actual Docling conversion on tiny, checked-in PDF fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = Path(__file__).with_name("test_fixtures")
        cls.temporary = tempfile.TemporaryDirectory(prefix="geha-html-test-")
        cls.output_dir = Path(cls.temporary.name)
        converter = native_text_converter()
        fallback = ocr_table_converter()
        cls.numeric = extract_pdf(
            cls.fixtures / "table_numeric_header.pdf", cls.output_dir,
            converter, fallback,
        )
        cls.continuation = extract_pdf(
            cls.fixtures / "table_page_continuation.pdf", cls.output_dir,
            converter, fallback,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_pdf_numeric_header_is_promoted(self):
        self.assertEqual(self.numeric["tables_written"], 1)
        self.assertTrue(self.numeric["outputs"][0]["header_promoted"])
        html = (self.output_dir / self.numeric["outputs"][0]["html"]).read_text()
        self.assertIn("<th>Drug Name</th>", html)
        self.assertIn("<th>HCPCS Code</th>", html)
        self.assertNotIn("<th>0</th>", html)
        self.assertIn("Datroway", html)

    def test_pdf_page_continuation_restores_first_row(self):
        self.assertEqual(self.continuation["tables_written"], 2)
        continuation = self.continuation["outputs"][1]
        self.assertEqual(continuation["page"], 2)
        self.assertEqual(continuation["header_inherited_from_table"], 1)
        self.assertEqual(continuation["rows"], 2)
        html = (self.output_dir / continuation["html"]).read_text()
        self.assertIn("<th>Drug Name</th>", html)
        self.assertIn("<th>HCPCS Code</th>", html)
        self.assertIn("Zirabev", html)
        self.assertIn("Alymsys", html)


if __name__ == "__main__":
    unittest.main()
