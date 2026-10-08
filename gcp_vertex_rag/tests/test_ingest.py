from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ingest.__main__ import discover_pdfs, sha256


class IngestTests(unittest.TestCase):
    def test_discovers_only_pdfs_in_stable_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.pdf").write_bytes(b"b")
            (root / "a.pdf").write_bytes(b"a")
            (root / "notes.md").write_text("ignore", encoding="utf-8")
            self.assertEqual([path.name for path in discover_pdfs(root)], ["a.pdf", "b.pdf"])

    def test_sha256_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.pdf"
            path.write_bytes(b"policy")
            self.assertEqual(
                sha256(path), "823412d1eacb67956220e532959f0104603057c88704863ca38e7cd188fda812"
            )


if __name__ == "__main__":
    unittest.main()
