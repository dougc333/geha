"""Tests for the local extraction-review slideshow."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from artifact_slideshow import discover_artifacts, prepare_policy_artifacts, viewer_html


class ArtifactSlideshowTests(unittest.TestCase):
    def test_discovers_pages_and_docling_html_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "policy_images_2.png").write_bytes(b"png")
            (root / "policy_images_1.png").write_bytes(b"png")
            (root / "policy_docling_table_001_page_2.html").write_text("<table></table>")
            (root / "policy_pdfplumber_table_001_page_2.html").write_text("<table></table>")
            pages, tables = discover_artifacts(root)
            self.assertEqual(pages, ["/files/policy_images_1.png", "/files/policy_images_2.png"])
            self.assertEqual(tables, ["/files/policy_docling_table_001_page_2.html"])

    def test_policy_filter_and_recursive_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "review_runs" / "one"
            nested.mkdir(parents=True)
            (nested / "ziihera_images_1.png").write_bytes(b"png")
            (nested / "ziihera_docling_tables.html").write_text("<table></table>")
            self.assertEqual(discover_artifacts(root, policy="ziihera"), ([], []))
            pages, tables = discover_artifacts(root, recursive=True, policy="ziihera")
            self.assertEqual(len(pages), 1)
            self.assertEqual(len(tables), 1)

    def test_viewer_uses_requested_interval(self) -> None:
        result = viewer_html(["/files/page.png"], ["/files/table.html"], 3.0)
        self.assertIn("const intervalMs = 3000", result)
        self.assertIn("PDF source ↔ Docling HTML review", result)

    def test_missing_policy_artifacts_are_prepared_without_vision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "geha-coverage-policy-bendamustine.pdf"
            pdf.write_bytes(b"pdf")
            calls = []

            def runner(source: Path, output: Path, **kwargs: object) -> dict:
                calls.append((source, output, kwargs))
                output.mkdir(parents=True)
                (output / "geha-coverage-policy-bendamustine_images_1.png").write_bytes(b"png")
                (output / "geha-coverage-policy-bendamustine_docling_tables.html").write_text(
                    "<table></table>"
                )
                return {}

            output = prepare_policy_artifacts(
                root, "bendamustine", cache_root=root / "slideshow_cache", runner=runner
            )
            self.assertEqual(output.parent.name, "slideshow_cache")
            self.assertEqual(calls[0][0], pdf.resolve())
            self.assertEqual(calls[0][2], {"use_vision": False})

    def test_policy_filter_must_identify_one_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                prepare_policy_artifacts(root, "missing", runner=lambda *_args, **_kwargs: {})


if __name__ == "__main__":
    unittest.main()
