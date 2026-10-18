import json
import tempfile
import unittest
from pathlib import Path

from contextual_retrieval_dashboard.visual_context import (
    contextualize_visual_run,
    discover_visual_chunks,
)


class VisualContextTests(unittest.TestCase):
    def make_run(self, root: Path) -> Path:
        run = root / "saved-run"
        page = run / "pages" / "page-004"
        figure = page / "segments" / "figure-01"
        alias = page / "segments" / "fig-02"
        figure.mkdir(parents=True)
        alias.mkdir(parents=True)
        (page / "source.pdf").write_bytes(b"%PDF-1.4 test page")
        (figure / "iteration-01.png").write_bytes(b"old")
        (figure / "iteration-03.png").write_bytes(b"latest")
        (figure / "iteration-not-a-number.png").write_bytes(b"ignore")
        (alias / "iteration-02.png").write_bytes(b"alias")
        (figure / "native-evidence.json").write_text(
            json.dumps({"literal_text": "Figure 1 evidence"}), encoding="utf-8"
        )
        return run

    def test_discovers_highest_iteration_for_figure_and_fig_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            chunks = discover_visual_chunks(self.make_run(Path(directory)))

        self.assertEqual(len(chunks), 2)
        self.assertEqual(
            chunks[1]["chunk_image"],
            "pages/page-004/segments/figure-01/iteration-03.png",
        )
        self.assertEqual(chunks[1]["literal_text"], "Figure 1 evidence")

    def test_contextualization_checkpoints_and_reuses_matching_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = self.make_run(Path(directory))
            calls: list[tuple[str, str]] = []

            def generate(pdf: Path, image: Path) -> str:
                calls.append((pdf.name, image.name))
                return f"Context for {image.name}"

            output = contextualize_visual_run(
                run, model="test-model", generate_context=generate
            )
            records = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(records), 2)
            self.assertIn("Figure 1 evidence", records[1]["contextual_retrieval_text"])

            def fail_if_called(_: Path, __: Path) -> str:
                raise AssertionError("matching records should be reused")

            contextualize_visual_run(
                run, model="test-model", generate_context=fail_if_called
            )


if __name__ == "__main__":
    unittest.main()
