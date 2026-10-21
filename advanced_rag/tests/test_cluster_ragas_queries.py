from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "evals" / "generate_cluster_ragas_queries.py"
SPEC = importlib.util.spec_from_file_location("generate_cluster_ragas_queries", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ClusterRagasQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = MODULE.load_manifest(
            PROJECT_ROOT / "evals" / "cluster_manifest.json"
        )

    def test_manifest_has_one_document_query_per_pdf(self) -> None:
        self.assertEqual(len(self.manifest["documents"]), 50)
        self.assertEqual(
            len({item["path"] for item in self.manifest["documents"]}),
            50,
        )

    def test_tasks_contain_only_single_document_queries(self) -> None:
        samples = {
            item["path"]: MODULE.SourceSample(
                item["path"], item["cluster"], Path(item["path"]).name, "hash", ()
            )
            for item in self.manifest["documents"]
        }
        tasks = MODULE.build_tasks(self.manifest, samples)
        self.assertEqual(len(tasks), 50)
        self.assertTrue(all(kind == "single_document" for _, kind, _ in tasks))
        self.assertTrue(all(len(sources) == 1 for _, _, sources in tasks))

    def test_single_document_validation_requires_grounded_evidence(self) -> None:
        source_type = MODULE.SourceSample
        sources = [source_type(
            "a.pdf",
            "research",
            "a.pdf",
            "a",
            ({"page": 1, "text": "Alpha evidence is present in source A."},),
        )]
        valid = {
            "question": "What does alpha show?",
            "reference_answer": "Alpha.",
            "evidence": [
                {"source_label": "A", "page": 1, "quote": "Alpha evidence is present"},
            ],
        }
        MODULE.validate_generation(valid, sources)
        invalid = json.loads(json.dumps(valid))
        invalid["evidence"][0]["quote"] = "This text is not present."
        with self.assertRaises(ValueError):
            MODULE.validate_generation(invalid, sources)

    def test_evidence_matching_tolerates_only_formatting_differences(self) -> None:
        source = MODULE.SourceSample(
            "a.pdf",
            "research",
            "a.pdf",
            "a",
            ({"page": 1, "text": "Adults aged 65–74: 12.5% reported improvement."},),
        )
        self.assertTrue(
            MODULE._quote_is_grounded(
                "Adults aged 65-74: 12.5% reported improvement.", source, 1
            )
        )
        self.assertFalse(
            MODULE._quote_is_grounded(
                "Adults aged 65-74 reported a major decline.", source, 1
            )
        )

    def test_evidence_candidates_are_exact_source_passages(self) -> None:
        source = MODULE.SourceSample(
            "a.pdf",
            "research",
            "a.pdf",
            "a",
            (
                {"page": 1, "text": "First exact passage."},
                {"page": 4, "text": "Second exact passage."},
            ),
        )
        candidates = MODULE.evidence_candidates([source])
        self.assertEqual(candidates["A1"]["quote"], "First exact passage.")
        self.assertEqual(candidates["A2"]["page"], 4)

    def test_writes_one_ragas_file_per_document(self) -> None:
        records = [
            {
                "id": "single-001",
                "source_documents": [{"path": "example.org/reports/alpha.pdf"}],
            },
            {
                "id": "single-002",
                "source_documents": [{"path": "example.org/reports/beta.pdf"}],
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = MODULE.write_per_document_files(root, records)
            self.assertEqual(len(outputs), 2)
            self.assertEqual(
                outputs[0],
                root / "example.org" / "reports" / "alpha" / "ragas.jsonl",
            )
            self.assertEqual(MODULE.read_jsonl(outputs[0]), [records[0]])
            self.assertEqual(MODULE.read_jsonl(outputs[1]), [records[1]])

    def test_rejects_unsafe_per_document_source_path(self) -> None:
        with self.assertRaises(ValueError):
            MODULE.per_document_output_path(Path("output"), "../outside.pdf")


if __name__ == "__main__":
    unittest.main()
