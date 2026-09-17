"""Tests for the standalone policy-document TF-IDF baseline."""

import tempfile
import unittest
from pathlib import Path

from tfidf_policy_search import TfidfPolicySearch, load_policies, without_revision_history


class TfidfPolicySearchTests(unittest.TestCase):
    def test_revision_table_without_heading_is_excluded(self) -> None:
        markdown = """# Nplate
## Approval criteria
Chemotherapy-induced thrombocytopenia
| Date | !Updates |
|------|----------|
| 2025 | Annual Review |
## Billing
J2802
"""
        cleaned = without_revision_history(markdown)
        self.assertIn("thrombocytopenia", cleaned)
        self.assertIn("J2802", cleaned)
        self.assertNotIn("Annual Review", cleaned)
        self.assertNotIn("Date |", cleaned)


    def test_revision_heading_is_excluded(self) -> None:
        markdown = "# Policy\n## Revision History\nChanged code\n## Billing\nJ2802"
        cleaned = without_revision_history(markdown)
        self.assertNotIn("Changed code", cleaned)
        self.assertIn("J2802", cleaned)


    def test_tfidf_ranks_policy_and_skips_nested_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            directory = Path(temporary_dir)
            (directory / "geha-coverage-policy-nplate.docling.md").write_text(
                "# Nplate\nChemotherapy-induced thrombocytopenia\n"
                "| Date | Updates |\n|---|---|\n| 2025 | Annual Review |",
                encoding="utf-8",
            )
            (directory / "geha-coverage-policy-ziihera.docling.md").write_text(
                "# Ziihera\nBiliary tract cancer", encoding="utf-8"
            )
            nested = directory / "archive"
            nested.mkdir()
            (nested / "geha-coverage-policy-other.docling.md").write_text(
                "thrombocytopenia", encoding="utf-8"
            )

            documents = load_policies(directory)
            self.assertEqual(len(documents), 2)
            self.assertTrue(all("Annual Review" not in doc.text for doc in documents))
            searcher = TfidfPolicySearch(documents)
            self.assertTrue(
                searcher.search("chemotherapy-induced thrombocytopenia")[0]
                .source_pdf.endswith("nplate.pdf")
            )
            self.assertTrue(
                searcher.search("biliary tract cancer")[0].source_pdf.endswith("ziihera.pdf")
            )
            self.assertEqual(searcher.search("nonexistentword"), [])


if __name__ == "__main__":
    unittest.main()
