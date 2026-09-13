import tempfile
import unittest
from pathlib import Path

from chunking_benchmarks.table_rag import (
    infer_title,
    normalized_table,
    split_csv_tables,
)


class TableRagTests(unittest.TestCase):
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

    def test_infers_billing_title(self):
        self.assertEqual(
            infer_title(["Drug Name", "HCPCS Code", "Description"]),
            "Billing codes",
        )


if __name__ == "__main__":
    unittest.main()
