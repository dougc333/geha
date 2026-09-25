import unittest

from single_page_table_graph import normalize_revision_tables


class RevisionTableNormalizationTests(unittest.TestCase):
    def test_restores_date_header_as_first_revision_row(self):
        tables = [{
            "extractor": "docling",
            "number": 1,
            "page": 49,
            "markdown": "",
            "columns": ["January 2024", "Origination"],
            "rows": [["March 2024", "Updated definition"]],
            "nearest_heading": "Policy History/Revision Information",
        }]

        normalized, stats = normalize_revision_tables(tables)

        self.assertEqual(normalized[0]["columns"], ["Date", "Updates"])
        self.assertEqual(
            normalized[0]["rows"][0], ["January 2024", "Origination"]
        )
        self.assertEqual(stats["raw_revision_rows"], 1)
        self.assertEqual(stats["restored_revision_rows"], 1)
        self.assertEqual(stats["normalized_revision_rows"], 2)
        self.assertEqual(tables[0]["columns"], ["January 2024", "Origination"])

    def test_preserves_explicit_date_updates_header(self):
        tables = [{
            "extractor": "docling",
            "number": 1,
            "page": 3,
            "markdown": "",
            "columns": ["Date", "Updates"],
            "rows": [["6/26/22", "Policy Creation"]],
            "nearest_heading": "For Internal Use ONLY",
        }]

        normalized, stats = normalize_revision_tables(tables)

        self.assertEqual(normalized[0]["rows"], [["6/26/22", "Policy Creation"]])
        self.assertEqual(stats["restored_revision_rows"], 0)
        self.assertEqual(stats["normalized_revision_rows"], 1)

    def test_does_not_modify_non_revision_table(self):
        tables = [{
            "extractor": "docling",
            "number": 1,
            "page": 2,
            "markdown": "",
            "columns": ["Drug Name", "HCPCS Code"],
            "rows": [["Example", "J0000"]],
            "nearest_heading": "Billing",
        }]

        normalized, stats = normalize_revision_tables(tables)

        self.assertEqual(normalized, tables)
        self.assertEqual(stats["revision_table_count"], 0)


if __name__ == "__main__":
    unittest.main()
