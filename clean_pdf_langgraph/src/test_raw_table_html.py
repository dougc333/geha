"""Tests that raw HTML shows, rather than repairs, extraction defects."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from .cleaning_graph import PDF_DIR
from .extract_pdfplumber_tables_html import extract_pdfplumber_tables_html
from .raw_table_html import save_raw_tables, standalone_raw_html


class RawTableHtmlTests(unittest.TestCase):
    def test_numeric_columns_and_embedded_header_remain_raw(self) -> None:
        frame = pd.DataFrame([["Drug Name", "HCPCS Code"], ["Ziihera", "J9276"]])
        source = standalone_raw_html(
            source="policy.pdf", extractor="pdfplumber", number=1, page=2,
            frame=frame,
        )
        self.assertIn("<style>", source)
        self.assertIn("<th>0</th>", source)
        self.assertIn("<th>1</th>", source)
        self.assertIn("<td>Drug Name</td>", source)
        self.assertIn("<td>HCPCS Code</td>", source)

    def test_page_fragments_are_separate_and_not_overwritten(self) -> None:
        frame = pd.DataFrame([["a", "b"]])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "policy.pdf"
            paths = save_raw_tables(
                source, directory, "pdfplumber", [(1, frame), (2, frame)]
            )
            self.assertEqual(len(paths), 2)
            self.assertNotEqual(paths[0], paths[1])
            self.assertIn("page_2", paths[1].name)
            with self.assertRaises(FileExistsError):
                save_raw_tables(source, directory, "pdfplumber", [(1, frame)])

    def test_real_pdfplumber_output_keeps_numeric_headers(self) -> None:
        sample = PDF_DIR / "geha-coverage-policy-ziihera.pdf"
        with tempfile.TemporaryDirectory() as temporary:
            paths = extract_pdfplumber_tables_html(sample, Path(temporary))
            self.assertGreater(len(paths), 0)
            self.assertIn("<th>0</th>", paths[0].read_text())


if __name__ == "__main__":
    unittest.main()
