from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from pypdf import PdfWriter

    from aws_data_workflow.server import (
        DocumentStore,
        create_app,
        load_query_examples,
        seed_corpus_documents,
    )
except ImportError:  # pragma: no cover - dependency-aware local test suite
    TestClient = None


@unittest.skipIf(TestClient is None, "server dependencies are not installed")
class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.client = TestClient(create_app(data_root=self.root, mode="simulate", seed_test_pdfs=False))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def pdf_bytes(self) -> bytes:
        path = self.root / "fixture.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with path.open("wb") as stream:
            writer.write(stream)
        return path.read_bytes()

    def test_query_examples_are_balanced_and_capped_at_thirty(self) -> None:
        path = self.root / "queries.jsonl"
        records = [
            {"id": f"a-{index}", "cluster": "a", "user_input": f"A question {index}"}
            for index in range(40)
        ] + [
            {"id": f"b-{index}", "cluster": "b", "user_input": f"B question {index}"}
            for index in range(40)
        ]
        path.write_text(
            "\n".join(json.dumps(record) for record in records),
            encoding="utf-8",
        )
        examples = load_query_examples(path, limit=100)
        self.assertEqual(len(examples), 30)
        self.assertEqual({item["cluster"] for item in examples}, {"a", "b"})
        self.assertEqual(examples[0]["cluster"], "a")
        self.assertEqual(examples[1]["cluster"], "b")

    def test_upload_persists_pdf_and_record(self) -> None:
        response = self.client.post(
            "/api/documents",
            files=[("files", ("policy.pdf", self.pdf_bytes(), "application/pdf"))],
        )
        self.assertEqual(response.status_code, 201)
        record = response.json()[0]
        self.assertEqual(record["stage"], "queued")
        self.assertEqual(record["pages"], 1)
        directory = self.root / "documents" / record["id"]
        self.assertTrue((directory / "source.pdf").is_file())
        self.assertTrue((directory / "pages" / "page-001" / "source.pdf").is_file())
        self.assertEqual(
            record["pagePreparation"],
            {"status": "ready", "completed": 1, "total": 1},
        )
        self.assertTrue((directory / "job.json").is_file())

    def test_document_list_reports_extraction_readiness_without_selection(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("extracted.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        pages = self.root / "documents" / uploaded["id"] / "pages"
        (pages / "page-001" / "docling.md").write_text(
            "Extracted page text", encoding="utf-8"
        )
        (pages / "docling-preflight.json").write_text(
            json.dumps({"page_count": 1, "completed_pages": 1}),
            encoding="utf-8",
        )

        records = self.client.get("/api/documents").json()
        listed = next(record for record in records if record["id"] == uploaded["id"])
        self.assertEqual(listed["sourceExtractionStatus"], "complete")
        self.assertEqual(listed["extractedPages"], 1)

        detail = self.client.get(f"/api/documents/{uploaded['id']}").json()
        self.assertEqual(detail["sourceExtractionStatus"], "complete")

    def test_seed_corpus_tops_up_without_duplicates(self) -> None:
        corpus = self.root / "corpus"
        corpus.mkdir()
        payload = self.pdf_bytes()
        for index in range(4):
            (corpus / f"document-{index}.pdf").write_bytes(payload)
        store = DocumentStore(self.root / "seed-runtime")

        self.assertEqual(seed_corpus_documents(store, corpus, 2), 2)
        self.assertEqual(seed_corpus_documents(store, corpus, 4), 2)
        self.assertEqual(seed_corpus_documents(store, corpus, 4), 0)
        records = store.list()
        self.assertEqual(len(records), 4)
        self.assertEqual(
            {record["seedSource"] for record in records},
            {f"document-{index}.pdf" for index in range(4)},
        )

    def test_batch_processes_document_to_completion(self) -> None:
        upload = self.client.post(
            "/api/documents",
            files=[("files", ("coverage-policy.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        response = self.client.post("/api/jobs/run-next")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["submitted"], 1)
        self.assertEqual(response.json()["documentId"], upload["id"])
        deadline = time.monotonic() + 6
        record = upload
        while time.monotonic() < deadline:
            record = self.client.get(f"/api/documents/{upload['id']}").json()
            if record["stage"] == "complete":
                break
            time.sleep(0.1)
        self.assertEqual(record["stage"], "complete")
        self.assertEqual(record["route"], "policy_rag")

    def test_startup_recovers_interrupted_running_job(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("interrupted.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        store = self.client.app.state.store
        store.save({**store.get(uploaded["id"]), "stage": "extracting", "status": "running"})

        restarted = TestClient(create_app(data_root=self.root, mode="docling", seed_test_pdfs=False))
        recovered = restarted.get(f"/api/documents/{uploaded['id']}").json()
        self.assertEqual(recovered["stage"], "queued")
        self.assertEqual(recovered["status"], "queued")

    def test_run_next_submits_only_one_document(self) -> None:
        for name in ("first.pdf", "second.pdf"):
            self.client.post(
                "/api/documents",
                files=[("files", (name, self.pdf_bytes(), "application/pdf"))],
            )

        first = self.client.post("/api/jobs/run-next")
        second = self.client.post("/api/jobs/run-next")
        self.assertEqual(first.json()["submitted"], 1)
        self.assertIsNotNone(first.json()["documentId"])
        self.assertEqual(second.json()["submitted"], 0)
        self.assertIsNone(second.json()["documentId"])
        deadline = time.monotonic() + 1
        records = self.client.get("/api/documents").json()
        while sum(record["stage"] == "queued" for record in records) == 2 and time.monotonic() < deadline:
            time.sleep(0.01)
            records = self.client.get("/api/documents").json()
        self.assertEqual(sum(record["stage"] == "queued" for record in records), 1)

    def test_run_next_records_selected_ocr_engine(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("engine.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        response = self.client.post(
            "/api/jobs/run-next",
            json={"ocr_engine": "llamaparse"},
        )
        self.assertEqual(response.status_code, 202)
        deadline = time.monotonic() + 1
        record = self.client.get(f"/api/documents/{uploaded['id']}").json()
        while "ocrEngine" not in record and time.monotonic() < deadline:
            time.sleep(0.01)
            record = self.client.get(f"/api/documents/{uploaded['id']}").json()
        self.assertEqual(record["ocrEngine"], "llamaparse")

    def test_run_document_resets_failed_selected_record(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("selected.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        store = self.client.app.state.store
        store.save({
            **store.get(uploaded["id"]),
            "stage": "extracting",
            "progress": 29,
            "status": "failed",
            "error": "old failure",
        })
        response = self.client.post(
            f"/api/documents/{uploaded['id']}/run",
            json={"ocr_engine": "llamaparse"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["submitted"])
        record = store.get(uploaded["id"])
        self.assertEqual(record["ocrEngine"], "llamaparse")
        self.assertNotEqual(record.get("error"), "old failure")

    def test_contextual_retrieval_runs_page_by_page_and_reports_status(self) -> None:
        calls: list[str] = []

        def generate(_document: str, chunk: str) -> dict[str, object]:
            calls.append(chunk)
            return {
                "context": "Coverage policy page context",
                "input_tokens": 20,
                "output_tokens": 5,
                "cache_creation_input_tokens": 200,
                "cache_read_input_tokens": 0,
            }

        client = TestClient(create_app(
            data_root=self.root / "contextual-api",
            mode="simulate",
            seed_test_pdfs=False,
            contextual_generate_context=generate,
        ))
        uploaded = client.post(
            "/api/documents",
            files=[("files", ("context.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        page_dir = (
            client.app.state.store.directory(uploaded["id"])
            / "pages"
            / "page-001"
        )
        (page_dir / "docling.md").write_text("Page evidence", encoding="utf-8")

        idle = client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval"
        )
        self.assertEqual(idle.status_code, 200)
        self.assertEqual(idle.json()["total_pages"], 1)
        denied = client.post(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/run",
            json={"confirm_cost": False},
        )
        self.assertEqual(denied.status_code, 400)
        started = client.post(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/run",
            json={"confirm_cost": True},
        )
        self.assertEqual(started.status_code, 202)
        deadline = time.monotonic() + 3
        status = idle.json()
        while time.monotonic() < deadline:
            status = client.get(
                f"/api/documents/{uploaded['id']}/contextual-retrieval"
            ).json()
            if status["status"] == "complete":
                break
            time.sleep(0.02)
        self.assertEqual(status["status"], "complete")
        self.assertEqual(status["completed_pages"], 1)
        self.assertEqual(calls, ["Page evidence"])
        document = client.get(f"/api/documents/{uploaded['id']}").json()
        self.assertEqual(document["contextStatus"], "contextualized")
        self.assertEqual(document["chunks"], 1)
        self.assertEqual(document["retrievalUnits"], 1)
        self.assertEqual(document["contextSources"], {"docling": 1})
        page = client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/pages/1"
        )
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["retrieval_context"], "Coverage policy page context")

    def test_contextual_retrieval_prefers_more_complete_document_pages(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("context.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        store = self.client.app.state.store
        document_dir = store.directory(uploaded["id"])
        document_pages = document_dir / "pages"
        (document_pages / "page-001" / "docling.md").write_text(
            "Stable page one", encoding="utf-8"
        )
        second_page = document_pages / "page-002"
        second_page.mkdir()
        (second_page / "docling.md").write_text(
            "Stable page two", encoding="utf-8"
        )

        run_id = "ingestion-20261020T010203Z-partial"
        run_dir = self.root / "runs" / "documents" / "context" / run_id
        run_page = run_dir / "pages" / "page-001"
        run_page.mkdir(parents=True)
        (run_page / "llamaparse.md").write_text(
            "Stale partial page", encoding="utf-8"
        )
        store.save({
            **store.get(uploaded["id"]),
            "ocrEngine": "llamaparse",
            "runDirectory": str(run_dir.relative_to(self.root)),
        })

        status = self.client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval"
        ).json()
        self.assertEqual(status["total_pages"], 2)
        self.assertEqual(
            [page["source_markdown"] for page in status["pages"]],
            ["pages/page-001/docling.md", "pages/page-002/docling.md"],
        )
        source = self.client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/pages/2/source"
        )
        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.text, "Stable page two")

    def test_contextual_judge_reports_page_integrity_and_progress(self) -> None:
        def generate_context(_document: str, _chunk: str) -> str:
            return "This page describes plan enrollment."

        def generate_judgment(_source: str, _context: str) -> dict[str, object]:
            return {
                "verdict": "review",
                "source_integrity": "suspect",
                "context_grounding": "grounded",
                "source_issues": ["Numeric table headers may be synthetic"],
                "context_issues": [],
                "rationale": "The context is supported, but the table needs review.",
                "confidence": 0.91,
            }

        client = TestClient(create_app(
            data_root=self.root / "judge-api",
            mode="simulate",
            seed_test_pdfs=False,
            contextual_generate_context=generate_context,
            contextual_generate_judgment=generate_judgment,
        ))
        uploaded = client.post(
            "/api/documents",
            files=[("files", ("judge.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        page_dir = client.app.state.store.directory(uploaded["id"]) / "pages" / "page-001"
        (page_dir / "docling.md").write_text("| 0 | 1 | 2 |", encoding="utf-8")

        client.post(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/run",
            json={"confirm_cost": True},
        )
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if client.get(f"/api/documents/{uploaded['id']}/contextual-retrieval").json()["status"] == "complete":
                break
            time.sleep(0.02)

        started = client.post(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/judge/run",
            json={"confirm_cost": True},
        )
        self.assertEqual(started.status_code, 202)
        judge = {}
        while time.monotonic() < deadline:
            judge = client.get(
                f"/api/documents/{uploaded['id']}/contextual-retrieval/judge"
            ).json()
            if judge["status"] == "complete":
                break
            time.sleep(0.02)
        self.assertEqual(judge["completed_pages"], 1)
        self.assertEqual(judge["counts"]["review"], 1)
        document = client.get(f"/api/documents/{uploaded['id']}").json()
        self.assertEqual(document["contextStatus"], "judged")
        page = client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/judge/pages/1"
        ).json()
        self.assertEqual(page["source_integrity"], "suspect")
        self.assertEqual(page["context_grounding"], "grounded")

    def test_form_contextual_retrieval_is_one_vector_linked_to_source(self) -> None:
        client = TestClient(create_app(
            data_root=self.root / "form-contextual-api",
            mode="simulate",
            seed_test_pdfs=False,
            contextual_generate_form_context=lambda _document: "Complete application context",
            contextual_embed_form_text=lambda _text: [0.2, 0.4],
        ))
        uploaded = client.post(
            "/api/documents",
            files=[(
                "files",
                (
                    "Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf",
                    self.pdf_bytes(),
                    "application/pdf",
                ),
            )],
        ).json()[0]
        self.assertEqual(uploaded["route"], "whole_document_context")
        self.assertEqual(uploaded["retrievalUnits"], 1)
        page_dir = (
            client.app.state.store.directory(uploaded["id"])
            / "pages"
            / "page-001"
        )
        (page_dir / "docling.md").write_text(
            "Application for One Person", encoding="utf-8"
        )

        idle = client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval"
        ).json()
        self.assertEqual(idle["storage_strategy"], "whole_document")
        self.assertEqual(idle["total_pages"], 1)
        started = client.post(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/run",
            json={"confirm_cost": True},
        )
        self.assertEqual(started.status_code, 202)
        deadline = time.monotonic() + 3
        status = idle
        while time.monotonic() < deadline:
            status = client.get(
                f"/api/documents/{uploaded['id']}/contextual-retrieval"
            ).json()
            if status["status"] == "complete":
                break
            time.sleep(0.02)
        self.assertEqual(status["status"], "complete")
        self.assertEqual(status["retrieval_units"], 1)
        vectors = client.get("/api/vector-db/forms").json()
        self.assertEqual(len(vectors), 1)
        self.assertEqual(vectors[0]["source_uri"], f"/api/documents/{uploaded['id']}/source")
        contextual = client.get(
            f"/api/documents/{uploaded['id']}/contextual-retrieval/pages/1"
        ).json()
        self.assertEqual(contextual["text"].count("Application for One Person"), 1)
        source = client.get(vectors[0]["source_uri"])
        self.assertEqual(source.status_code, 200)

    def test_document_runs_lists_owned_runs_and_historical_artifacts(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("history.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        store = self.client.app.state.store
        run_id = "ingestion-20261020T010203Z-abc123"
        run_dir = self.root / "runs" / "documents" / "history" / run_id
        page_dir = run_dir / "pages" / "page-001"
        page_dir.mkdir(parents=True)
        (run_dir / "input").mkdir()
        (run_dir / "input" / "source.pdf").write_bytes(self.pdf_bytes())
        (page_dir / "docling.md").write_text("# Historical page\n", encoding="utf-8")
        page_item = {
            "page": 1,
            "source_image": None,
            "docling_markdown": "page-001/docling.md",
            "deepseek_markdown": None,
            "llamaparse_markdown": None,
            "ocr_engine": "deepseek",
            "ocr_markdown": None,
            "markdown_source": "docling",
            "issues": ["deepseek_unavailable"],
        }
        (page_dir / "page-manifest.json").write_text(json.dumps(page_item), encoding="utf-8")
        (run_dir / "run-manifest.json").write_text(json.dumps({
            "document_id": uploaded["id"],
            "run_id": run_id,
            "created_at": "2026-10-20T01:02:03+00:00",
            "completed_at": "2026-10-20T01:02:04+00:00",
            "ocr_engine": "deepseek",
            "result": {"pages": {"page_count": 1, "ocr_pages": 0, "issue_count": 1}},
        }), encoding="utf-8")
        store.save({**store.get(uploaded["id"]), "runId": run_id})

        runs = self.client.get(f"/api/documents/{uploaded['id']}/runs")
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.json()[0]["run_id"], run_id)
        self.assertTrue(runs.json()[0]["is_current"])
        manifest = self.client.get(
            f"/api/documents/{uploaded['id']}/runs/{run_id}/page-manifest"
        )
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.json()["summary"]["issue_count"], 1)
        artifact = self.client.get(
            f"/api/documents/{uploaded['id']}/runs/{run_id}/artifacts/pages/page-001/docling.md"
        )
        self.assertEqual(artifact.text, "# Historical page\n")

    def test_incomplete_run_serves_matching_page_pdf_and_llamaparse_markdown(self) -> None:
        uploaded = self.client.post(
            "/api/documents",
            files=[("files", ("live.pdf", self.pdf_bytes(), "application/pdf"))],
        ).json()[0]
        store = self.client.app.state.store
        run_id = "ingestion-20261020T030000Z-live01"
        run_dir = self.root / "runs" / "documents" / "live" / run_id
        page_dir = run_dir / "pages" / "page-001"
        page_dir.mkdir(parents=True)
        page_pdf = self.root / "documents" / uploaded["id"] / "pages" / "page-001" / "source.pdf"
        (page_dir / "source.pdf").write_bytes(page_pdf.read_bytes())
        (page_dir / "llamaparse.md").write_text("# Live page\n", encoding="utf-8")
        store.save({
            **store.get(uploaded["id"]),
            "runId": run_id,
            "runDirectory": str(run_dir.relative_to(self.root)),
            "ocrEngine": "llamaparse",
            "stage": "extracting",
            "status": "running",
        })

        runs = self.client.get(f"/api/documents/{uploaded['id']}/runs")
        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.json()[0]["run_id"], run_id)
        self.assertEqual(runs.json()[0]["ocr_pages"], 1)
        manifest = self.client.get(
            f"/api/documents/{uploaded['id']}/runs/{run_id}/page-manifest"
        )
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(
            manifest.json()["pages"][0]["llamaparse_markdown"],
            "page-001/llamaparse.md",
        )
        source = self.client.get(
            f"/api/documents/{uploaded['id']}/runs/{run_id}/pages/1/source"
        )
        self.assertEqual(source.status_code, 200)
        self.assertEqual(source.headers["content-type"], "application/pdf")

    def test_cluster_inventory_and_query_router(self) -> None:
        clusters = self.client.get("/api/clusters")
        self.assertEqual(clusters.status_code, 200)
        self.assertEqual(sum(item["document_count"] for item in clusters.json()), 50)

        routed = self.client.post(
            "/api/query-router",
            json={"jsonl": '{"query":"What are the prior authorization criteria?"}'},
        )
        self.assertEqual(routed.status_code, 200)
        body = routed.json()
        self.assertEqual(body["status"], "routed")
        self.assertEqual(body["routes"][0]["cluster"], "policy")
        self.assertIn(body["router"]["mode"], {"jev", "deterministic_fallback"})
        self.assertTrue(body["run_id"].startswith("route-"))

        history = self.client.get("/api/query-router/runs")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["run_id"], body["run_id"])
        self.assertEqual(history.json()[0]["input_jsonl"], '{"query":"What are the prior authorization criteria?"}')

    def test_query_router_rejects_invalid_jsonl(self) -> None:
        response = self.client.post("/api/query-router", json={"jsonl": "not-json"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Line 1", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
