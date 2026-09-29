"""Figure chunks (local_ingest/describe_figures.py) with Nova Lite and S3 faked."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from support import load

describe_figures = load("describe_figures", "local_ingest/describe_figures.py")

DOC = "doc123"
USAGE = {"inputTokens": 100, "outputTokens": 20}


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        figure_dir = self.tmp / "figures" / DOC
        figure_dir.mkdir(parents=True)
        for name in ("p003_f01.png", "p005_f02.png"):
            (figure_dir / name).write_bytes(b"\x89PNG fake")
        (figure_dir / "figures.json").write_text(json.dumps([
            {"file": "p003_f01.png", "page": 3, "kind": "picture", "caption": "Figure 1: Model."},
            {"file": "p005_f02.png", "page": 5, "kind": "chart", "caption": ""},
        ]))
        base = {"document_id": DOC, "source": "docling:x.pdf", "title": "A Paper"}
        self.jsonl = self.tmp / f"{DOC}.jsonl"
        self.jsonl.write_text("\n".join(json.dumps({**base, "chunk_index": i, "page_number": 1,
                                                    "content": f"text {i}", "kind": "text"})
                                        for i in range(2)) + "\n")
        patcher = mock.patch.object(describe_figures, "OUT", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_process(self, **kwargs):
        with mock.patch.object(describe_figures, "describe",
                               return_value=("Text in figure: A | B", USAGE)) as describe:
            describe_figures.process(self.jsonl, kwargs.pop("s3", None), "bucket", **kwargs)
        return describe

    def lines(self) -> list[dict]:
        return [json.loads(l) for l in self.jsonl.read_text().splitlines()]

    def test_appends_one_chunk_per_figure(self):
        describe = self.run_process()
        self.assertEqual(describe.call_count, 2)
        figures = [l for l in self.lines() if l["kind"] == "figure"]
        self.assertEqual([f["chunk_index"] for f in figures], [2, 3])
        self.assertEqual([f["page_number"] for f in figures], [3, 5])
        self.assertEqual(figures[0]["image"], f"figures/{DOC}/p003_f01.png")
        self.assertEqual(figures[0]["content"],
                         'Figure (page 3) from "A Paper": Figure 1: Model.\nText in figure: A | B')

    def test_rerun_uses_cached_descriptions_and_replaces_chunks(self):
        self.run_process()
        describe = self.run_process()
        self.assertEqual(describe.call_count, 0)  # descriptions cached in figures.json
        self.assertEqual(sum(l["kind"] == "figure" for l in self.lines()), 2)  # not duplicated

    def test_redo_only_named_files(self):
        self.run_process()
        describe = self.run_process(redo=True, files={"p005_f02.png"})
        self.assertEqual(describe.call_count, 1)

    def test_upload_puts_images_before_jsonl(self):
        # The JSONL upload triggers the embedder; its figures must already be in S3.
        s3 = mock.Mock()
        self.run_process(s3=s3)
        keys = [c.args[2] for c in s3.upload_file.call_args_list]
        self.assertEqual(keys, [f"figures/{DOC}/p003_f01.png", f"figures/{DOC}/p005_f02.png",
                                f"chunks/{DOC}.jsonl"])

    def test_chunk_without_caption_or_text_section(self):
        chunk = describe_figures.figure_chunk("A Paper", {"page": 2, "caption": "", "description": "A plot."})
        self.assertEqual(chunk, 'Figure (page 2) from "A Paper"\nDescription: A plot.')


if __name__ == "__main__":
    unittest.main()
