from argparse import Namespace
import tempfile
import unittest
from pathlib import Path

from context_assembly_benchmarks.evaluate_chunking_judge import (
    prompt_hashes,
    resolve_artifact_paths,
)


class RunArtifactTests(unittest.TestCase):
    def test_run_dir_selects_isolated_artifact_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = (Path(directory) / "run-001").resolve()
            args = Namespace(
                run_dir=run_dir,
                partial=None,
                output=None,
                markdown=None,
            )

            resolve_artifact_paths(args)

            self.assertEqual(args.partial, run_dir / "partial.jsonl")
            self.assertEqual(args.output, run_dir / "results.json")
            self.assertEqual(args.markdown, run_dir / "results.md")
            self.assertEqual(args.manifest, run_dir / "run.json")
            self.assertTrue(run_dir.is_dir())

    def test_prompt_fingerprints_are_named_sha256_values(self):
        hashes = prompt_hashes()

        self.assertEqual(
            set(hashes),
            {
                "answer_prompt_sha256",
                "judge_prompt_sha256",
                "qualifier_fact_checker_sha256",
                "evaluation_pipeline_sha256",
            },
        )
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))
        self.assertTrue(all(set(value) <= set("0123456789abcdef") for value in hashes.values()))
