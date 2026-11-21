from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from geha_processing.io import atomic_json, atomic_jsonl, read_jsonl
from geha_processing.tables import (
    choose_replacement_headers,
    inherit_continuation_header,
    promote_embedded_header,
    table_headers_are_default,
)


class SharedProcessingTests(unittest.TestCase):
    def test_default_headers_do_not_match_years(self) -> None:
        self.assertTrue(table_headers_are_default(["0", "1", "2"]))
        self.assertTrue(table_headers_are_default(["Unnamed: 0", "Unnamed: 1"]))
        self.assertFalse(table_headers_are_default(["2025", "2023"]))

    def test_promotes_policy_header_row(self) -> None:
        frame = pd.DataFrame([
            ["Service Type", "Code", "Description"],
            ["Imaging", "58340", "Catheterization"],
        ])
        repaired, changed = promote_embedded_header(frame)
        self.assertTrue(changed)
        self.assertEqual(list(repaired.columns), ["Service Type", "Code", "Description"])

    def test_inherits_adjacent_continuation_header(self) -> None:
        previous = pd.DataFrame(
            [["Imaging", "58340", "Catheterization"]],
            columns=["Service Type", "Code", "Description"],
        )
        current = pd.DataFrame([["Lab", "81479", "Genetic testing"]])
        repaired, changed = inherit_continuation_header(
            current,
            previous,
            heading="Applicable Codes",
            previous_heading="Applicable Codes",
            page_number=26,
            previous_page=25,
        )
        self.assertTrue(changed)
        self.assertEqual(list(repaired.columns), list(previous.columns))

    def test_structured_header_choice_is_conservative(self) -> None:
        headers, method = choose_replacement_headers(
            ["0", "1", "2"],
            previous_headers=["Service Type", "Code", "Description"],
            page=26,
            previous_page=25,
        )
        self.assertEqual(headers, ["Service Type", "Code", "Description"])
        self.assertEqual(method, "inherited_previous_page")

    def test_atomic_io(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            atomic_json(root / "value.json", {"ok": True})
            atomic_jsonl(root / "rows.jsonl", [{"id": 1}, {"id": 2}])
            self.assertEqual(read_jsonl(root / "rows.jsonl"), [{"id": 1}, {"id": 2}])


if __name__ == "__main__":
    unittest.main()
