from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from .backend import _cloud_page_comparisons
from .s3_store import S3ArtifactStore


class CloudAdapterTests(unittest.TestCase):
    def test_s3_keys_keep_raw_and_run_hierarchy(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "runs" / "coverage-policies" / "geha-coverage-policy-datroway" / "agent-demo-1"
            page = run / "pages" / "page-001" / "final.html"
            page.parent.mkdir(parents=True)
            page.write_text("<p>test</p>")
            (run / "qc-report.json").write_text("{}")
            client = Mock()
            store = S3ArtifactStore(root, bucket="test-bucket", client=client)
            keys = store.upload_run(run)
            self.assertEqual(keys, [
                "runs/coverage-policies/geha-coverage-policy-datroway/agent-demo-1/pages/page-001/final.html",
                "runs/coverage-policies/geha-coverage-policy-datroway/agent-demo-1/qc-report.json",
            ])
            self.assertEqual(client.upload_file.call_count, 2)
            self.assertEqual(store.key_for(root / "raw" / "research" / "report.pdf"), "raw/research/report.pdf")
            with self.assertRaises(ValueError):
                store.key_for(root.parent / "outside.pdf")

    def test_saved_run_preview_uses_s3_metadata_and_artifact_paths(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "runs" / "research" / "example" / "agent-demo-1"
            store = Mock()
            store.key_for.return_value = "runs/research/example/agent-demo-1"
            store.get_json.return_value = {"tool_id": "authored_figure_spec_html"}
            prefix = "runs/research/example/agent-demo-1/pages/page-003/"
            keys = {prefix + name for name in ("source.pdf", "final.html", "page-manifest.json")}
            pages = _cloud_page_comparisons(run, keys, store)
            self.assertEqual(pages["3"]["after"]["tool_id"], "authored_figure_spec_html")
            self.assertEqual(pages["3"]["after"]["html"], str(run / "pages/page-003/final.html"))
            self.assertEqual(pages["3"]["before"]["html"], str(run / "pages/page-003/final.html"))


if __name__ == "__main__":
    unittest.main()
