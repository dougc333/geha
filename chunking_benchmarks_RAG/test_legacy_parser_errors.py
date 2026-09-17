"""Keep the pre-fix parsing examples stable for a future LangGraph demo."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


FIXTURES = Path(__file__).with_name("test_fixtures") / "legacy_parser_errors"
REPO_ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def headers(path: Path) -> list[str]:
    return re.findall(r"<th\b[^>]*>(.*?)</th>", path.read_text(encoding="utf-8"), re.DOTALL)


class LegacyParserErrorFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        cls.cases = {case["id"]: case for case in cls.manifest["cases"]}

    def test_archived_outputs_and_source_pdfs_are_unchanged(self):
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                source = REPO_ROOT / self.manifest["source_root"] / case["source_pdf"]
                self.assertEqual(digest(source), case["source_pdf_sha256"])
                legacy = FIXTURES / case["legacy_html"]
                self.assertEqual(digest(legacy), case["legacy_html_sha256"])
                if "first_fragment_html" in case:
                    first = FIXTURES / case["first_fragment_html"]
                    self.assertEqual(digest(first), case["first_fragment_html_sha256"])

    def test_datroway_header_is_still_broken_in_before_snapshot(self):
        case = self.cases["datroway_numeric_header"]
        legacy = FIXTURES / case["legacy_html"]
        self.assertEqual(headers(legacy), ["0", "1", "2"])
        body = legacy.read_text(encoding="utf-8")
        self.assertIn("<td>Drug Name</td>", body)
        self.assertIn("<td>HCPCS Code</td>", body)
        self.assertIn("<td>Datroway</td>", body)

    def test_bevacizumab_continuation_loses_headers_only(self):
        case = self.cases["bevacizumab_page_boundary"]
        first = FIXTURES / case["first_fragment_html"]
        continuation = FIXTURES / case["legacy_html"]
        self.assertEqual(headers(first), case["expected_headers"])
        self.assertEqual(headers(continuation), ["0", "1", "2"])
        body = continuation.read_text(encoding="utf-8")
        for value in ("Vegzelma", "Avzivi", "Jobeyne"):
            self.assertIn(value, body)


if __name__ == "__main__":
    unittest.main()
