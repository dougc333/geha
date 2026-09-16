import unittest

import pandas as pd

from chunking_benchmarks_RAG.extract_pdf_tables_html import (
    looks_like_revision_history,
    slugify,
    standalone_html,
)


class HtmlTableExtractionTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
