"""Read-only AWS runtime for Jev routing and prebuilt contextual embeddings."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .policy_rag import retrieve, source_pages
from .query_router import load_clusters, route_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = PROJECT_ROOT / "evals" / "cluster_manifest.json"
DEFAULT_QUERY_EXAMPLES = PROJECT_ROOT / "evals" / "generated" / "cluster_ragas_queries.jsonl"
DEFAULT_WEB_DIRECTORY = PROJECT_ROOT / "web" / "dist"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=6, ge=1, le=20)


class QueryRouterRequest(BaseModel):
    jsonl: str = Field(min_length=1, max_length=50_000)


def load_query_examples(path: Path, limit: int = 30) -> list[dict[str, Any]]:
    """Return the same cluster-balanced query projection as the local UI."""
    capped_limit = min(max(limit, 1), 30)
    grouped: dict[str, list[dict[str, Any]]] = {}
    if not path.is_file():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        query = str(record.get("user_input") or "").strip()
        cluster = str(record.get("cluster") or "unknown").strip()
        if not query:
            continue
        sources = record.get("source_documents") or []
        grouped.setdefault(cluster, []).append({
            "id": str(record.get("id") or f"{cluster}-{len(grouped.get(cluster, [])) + 1}"),
            "cluster": cluster,
            "user_input": query,
            "source_documents": [
                str(source.get("filename"))
                for source in sources
                if isinstance(source, dict) and source.get("filename")
            ],
        })

    examples: list[dict[str, Any]] = []
    offsets = {cluster: 0 for cluster in grouped}
    while len(examples) < capped_limit:
        added = False
        for cluster in sorted(grouped):
            offset = offsets[cluster]
            if offset < len(grouped[cluster]):
                examples.append(grouped[cluster][offset])
                offsets[cluster] += 1
                added = True
                if len(examples) == capped_limit:
                    break
        if not added:
            break
    return examples


def _document_clusters(manifest_path: Path) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        Path(item["path"]).name.lower(): item["cluster"]
        for item in manifest["documents"]
    }


class RuntimeIndex:
    """Load immutable, precomputed JSONL retrieval records from S3 or disk."""

    def __init__(
        self,
        *,
        manifest_path: Path = DEFAULT_MANIFEST,
        local_directory: Path | None = None,
        bucket: str | None = None,
        prefix: str = "indexes/",
        s3_client: Any | None = None,
    ) -> None:
        self.manifest_path = manifest_path
        self.local_directory = local_directory
        self.bucket = bucket
        self.prefix = prefix
        self.s3_client = s3_client
        self.records = self._load()

    def _load(self) -> list[dict[str, Any]]:
        payloads: list[tuple[str, str]] = []
        if self.local_directory:
            payloads.extend(
                (path.name, path.read_text(encoding="utf-8"))
                for path in sorted(self.local_directory.glob("*.jsonl"))
            )
        elif self.bucket:
            if self.s3_client is None:
                import boto3

                self.s3_client = boto3.client("s3")
            continuation = None
            while True:
                arguments = {"Bucket": self.bucket, "Prefix": self.prefix}
                if continuation:
                    arguments["ContinuationToken"] = continuation
                page = self.s3_client.list_objects_v2(**arguments)
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if key.endswith(".jsonl"):
                        body = self.s3_client.get_object(
                            Bucket=self.bucket, Key=key
                        )["Body"].read()
                        payloads.append((key, body.decode("utf-8")))
                if not page.get("IsTruncated"):
                    break
                continuation = page["NextContinuationToken"]

        clusters = _document_clusters(self.manifest_path)
        records: list[dict[str, Any]] = []
        for origin, payload in payloads:
            for line in payload.splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                source_name = str(record.get("source_name") or record.get("filename") or "")
                if not isinstance(record.get("embedding"), list):
                    continue
                records.append({
                    **record,
                    "cluster": record.get("cluster") or clusters.get(source_name.lower()),
                    "index_origin": origin,
                })
        return records


class BgeQueryEmbedder:
    """Lazily load the same compact BGE model used for the stored vectors."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        self.model_name = model_name
        self._model: Any | None = None
        self._lock = threading.Lock()

    def __call__(self, query: str) -> list[float]:
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
        vector = self._model.encode(query, normalize_embeddings=True)
        return [float(value) for value in vector]


class QueryRunStore:
    def __init__(self, table_name: str | None = None, table: Any | None = None) -> None:
        self.table_name = table_name
        self.table = table

    def save(self, result: dict[str, Any]) -> str:
        run_id = f"query-{uuid.uuid4().hex}"
        if self.table is None and self.table_name:
            import boto3

            self.table = boto3.resource("dynamodb").Table(self.table_name)
        if self.table is not None:
            self.table.put_item(Item={
                "id": run_id,
                "created_at": datetime.now(UTC).isoformat(),
                "payload": json.dumps(result, separators=(",", ":")),
            })
        return run_id

    def save_router(self, payload: str, result: dict[str, Any]) -> dict[str, Any]:
        created_at = datetime.now(UTC)
        run_id = f"route-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
        record = {
            **result,
            "run_id": run_id,
            "created_at": created_at.isoformat(),
            "input_jsonl": payload,
        }
        if self.table is None and self.table_name:
            import boto3

            self.table = boto3.resource("dynamodb").Table(self.table_name)
        if self.table is not None:
            self.table.put_item(Item={
                "id": run_id,
                "kind": "query_router",
                "created_at": record["created_at"],
                "payload": json.dumps(record, separators=(",", ":")),
            })
        return record

    def list_router(self, limit: int = 20) -> list[dict[str, Any]]:
        if self.table is None and self.table_name:
            import boto3

            self.table = boto3.resource("dynamodb").Table(self.table_name)
        if self.table is None or not hasattr(self.table, "scan"):
            return []
        response = self.table.scan()
        records: list[dict[str, Any]] = []
        for item in response.get("Items", []):
            if item.get("kind") != "query_router":
                continue
            try:
                records.append(json.loads(item["payload"]))
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
        return sorted(
            records,
            key=lambda record: str(record.get("created_at") or ""),
            reverse=True,
        )[:max(0, limit)]


def create_app(
    *,
    index: RuntimeIndex | None = None,
    embed_query: Callable[[str], list[float]] | None = None,
    run_store: QueryRunStore | None = None,
    web_directory: Path | None = DEFAULT_WEB_DIRECTORY,
) -> FastAPI:
    index = index or RuntimeIndex(
        bucket=os.environ.get("AWS_WORKFLOW_S3_BUCKET"),
        prefix=os.environ.get("AWS_RAG_INDEX_PREFIX", "indexes/"),
        local_directory=(
            Path(os.environ["AWS_RAG_INDEX_DIR"])
            if os.environ.get("AWS_RAG_INDEX_DIR")
            else None
        ),
    )
    embed_query = embed_query or BgeQueryEmbedder(
        os.environ.get("AWS_RAG_QUERY_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    )
    run_store = run_store or QueryRunStore(
        os.environ.get("AWS_WORKFLOW_DYNAMODB_TABLE")
    )
    allow_unreviewed = os.environ.get("AWS_RAG_ALLOW_UNREVIEWED", "0") == "1"

    app = FastAPI(title="GEHA Advanced RAG Runtime", version="1.0.0")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok" if index.records else "degraded",
            "mode": "prebuilt-contextual-embeddings",
            "docling": False,
            "generationModel": False,
            "records": len(index.records),
        }

    @app.get("/api/clusters")
    def clusters() -> list[dict[str, Any]]:
        return load_clusters(index.manifest_path)

    @app.get("/api/query-examples")
    def query_examples(limit: int = 30) -> list[dict[str, Any]]:
        return load_query_examples(DEFAULT_QUERY_EXAMPLES, limit=limit)

    @app.get("/api/query-router/runs")
    def query_router_runs(limit: int = 20) -> list[dict[str, Any]]:
        return run_store.list_router(min(max(limit, 1), 100))

    @app.post("/api/query-router")
    def query_router(request: QueryRouterRequest) -> dict[str, Any]:
        result = route_jsonl(request.jsonl, index.manifest_path)
        if result["status"] == "failed":
            raise HTTPException(status_code=422, detail=result.get("error"))
        return run_store.save_router(request.jsonl, result)

    @app.get("/api/documents")
    def documents() -> list[dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        for position, record in enumerate(index.records, start=1):
            document_id = str(
                record.get("document_id")
                or str(record.get("chunk_id") or "").split(":", 1)[0]
                or f"document-{position}"
            )
            filename = str(record.get("source_name") or record.get("filename") or document_id)
            records.setdefault(document_id, {
                "id": document_id,
                "filename": filename,
                "sizeMb": 0,
                "pages": len(source_pages(record)),
                "stage": "complete",
                "progress": 100,
                "route": "whole_document_context",
                "storageStrategy": "whole_document",
                "retrievalUnits": 1,
                "contextStatus": "contextualized",
                "embeddingDimensions": len(record.get("embedding") or []),
                "chunks": 1,
                "reviewIssues": 0 if record.get("review_status") == "approved" else 1,
                "status": "succeeded",
                "updatedAt": str(record.get("updated_at") or datetime.now(UTC).isoformat()),
            })
        return list(records.values())

    @app.get("/api/runtime/indexes")
    def runtime_indexes() -> list[dict[str, Any]]:
        return [
            {
                "document_id": str(
                    record.get("document_id")
                    or str(record.get("chunk_id") or "").split(":", 1)[0]
                ),
                "chunk_id": str(record.get("chunk_id") or ""),
                "filename": str(record.get("source_name") or record.get("filename") or ""),
                "cluster": record.get("cluster"),
                "pages": source_pages(record),
                "text": str(record.get("text") or ""),
                "retrieval_context": str(record.get("retrieval_context") or ""),
                "contextual_retrieval_text": str(
                    record.get("contextual_retrieval_text") or record.get("text") or ""
                ),
                "embedding_model": str(record.get("embedding_model") or "BAAI/bge-small-en-v1.5"),
                "embedding_dimensions": len(record.get("embedding") or []),
                "review_status": str(record.get("review_status") or "pending"),
            }
            for record in index.records
        ]

    @app.post("/api/search")
    def search(request: SearchRequest, http_response: Response) -> dict[str, Any]:
        request_started = time.perf_counter()
        route_started = time.perf_counter()
        routed = route_jsonl(
            json.dumps({"query": request.query}), index.manifest_path
        )
        route_ms = (time.perf_counter() - route_started) * 1_000
        if routed["status"] != "routed":
            raise HTTPException(status_code=422, detail=routed.get("error"))
        route = routed["routes"][0]
        candidates = [
            record for record in index.records
            if record.get("cluster") == route["cluster"]
        ]
        embedding_ms = 0.0

        def timed_embed(query: str) -> list[float]:
            nonlocal embedding_ms
            started = time.perf_counter()
            vector = embed_query(query)
            embedding_ms += (time.perf_counter() - started) * 1_000
            return vector

        retrieval_started = time.perf_counter()
        sources = retrieve(
            request.query,
            candidates,
            embed_query=timed_embed,
            top_k=request.top_k,
            allow_unreviewed=allow_unreviewed,
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1_000
        result = {
            "query": request.query,
            "route": route,
            "sources": [
                {
                    "rank": source["retrieval_rank"],
                    "score": source["retrieval_score"],
                    "chunk_id": source["chunk_id"],
                    "source_name": source.get("source_name"),
                    "pages": source_pages(source),
                    "text": source["text"],
                }
                for source in sources
            ],
        }
        persistence_started = time.perf_counter()
        run_id = run_store.save(result)
        persistence_ms = (time.perf_counter() - persistence_started) * 1_000
        total_ms = (time.perf_counter() - request_started) * 1_000
        latency = {
            "route_ms": round(route_ms, 2),
            "query_embedding_ms": round(embedding_ms, 2),
            "rank_fusion_ms": round(max(0.0, retrieval_ms - embedding_ms), 2),
            "retrieval_ms": round(retrieval_ms, 2),
            "persistence_ms": round(persistence_ms, 2),
            "total_ms": round(total_ms, 2),
        }
        http_response.headers["Server-Timing"] = ", ".join(
            f"{name.removesuffix('_ms')};dur={duration}"
            for name, duration in latency.items()
        )
        return {**result, "run_id": run_id, "latency_ms": latency}

    if web_directory is not None and (web_directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=web_directory, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        def browser() -> str:
            return """<!doctype html><meta charset=utf-8><title>GEHA Advanced RAG</title>
<style>body{font:16px system-ui;max-width:900px;margin:48px auto;padding:0 20px}input{width:75%;padding:10px}button{padding:10px 18px}pre{white-space:pre-wrap;background:#f4f4f4;padding:16px}</style>
<h1>GEHA Advanced RAG</h1><p>Jev routing + hybrid retrieval over prebuilt contextual embeddings. No Docling or answer-generation model runs here.</p>
<form id=f><input id=q placeholder="Ask a retrieval question" required><button>Search</button></form><pre id=o>Ready.</pre>
<script>f.onsubmit=async(e)=>{e.preventDefault();o.textContent='Searching…';let r=await fetch('/api/search',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:q.value})});o.textContent=JSON.stringify(await r.json(),null,2)}</script>"""

    return app


app = create_app()
