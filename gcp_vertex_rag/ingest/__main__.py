"""Upload coverage PDFs and import them into a Vertex AI RAG corpus."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def discover_pdfs(source: Path) -> list[Path]:
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    files = sorted(path for path in source.glob("*.pdf") if path.is_file())
    if not files:
        raise ValueError(f"No PDF files found in {source}")
    return files


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def upload_pdfs(project: str, bucket_name: str, source: Path) -> int:
    from google.cloud import storage

    client = storage.Client(project=project)
    bucket = client.bucket(bucket_name)
    count = 0
    for path in discover_pdfs(source):
        object_name = f"coverage-policies/{path.name}"
        blob = bucket.blob(object_name)
        checksum = sha256(path)
        if blob.exists(client) and blob.metadata and blob.metadata.get("sha256") == checksum:
            print(f"unchanged gs://{bucket_name}/{object_name}")
            continue
        blob.metadata = {"sha256": checksum, "classification": "public-demo-policy"}
        blob.upload_from_filename(path, content_type="application/pdf", checksum="auto")
        print(f"uploaded gs://{bucket_name}/{object_name}")
        count += 1
    return count


def get_or_create_corpus(project: str, location: str, display_name: str) -> str:
    import vertexai
    from vertexai import rag

    vertexai.init(project=project, location=location)
    for corpus in rag.list_corpora():
        if corpus.display_name == display_name:
            return corpus.name

    embedding = rag.RagEmbeddingModelConfig(
        vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
            publisher_model="publishers/google/models/text-embedding-005"
        )
    )
    corpus = rag.create_corpus(
        display_name=display_name,
        description="GEHA coverage-policy demonstration corpus; no member or claims data",
        backend_config=rag.RagVectorDbConfig(rag_embedding_model_config=embedding),
    )
    return corpus.name


def import_bucket(corpus_name: str, bucket_name: str) -> int:
    from vertexai import rag

    response = rag.import_files(
        corpus_name=corpus_name,
        paths=[f"gs://{bucket_name}/coverage-policies/"],
        transformation_config=rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(chunk_size=512, chunk_overlap=100)
        ),
        max_embedding_requests_per_min=900,
    )
    return int(response.imported_rag_files_count)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--source", type=Path, default=Path("../downloads/coverage-policies"))
    parser.add_argument("--corpus-display-name", default="geha-coverage-policies-demo")
    parser.add_argument("--upload-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uploaded = upload_pdfs(args.project, args.bucket, args.source)
    print(f"Uploaded or replaced {uploaded} PDF file(s).")
    if args.upload_only:
        return
    corpus_name = get_or_create_corpus(args.project, args.location, args.corpus_display_name)
    imported = import_bucket(corpus_name, args.bucket)
    print(f"Imported {imported} file(s) into {corpus_name}")
    print(f"Set VERTEX_RAG_CORPUS={corpus_name}")


if __name__ == "__main__":
    main()

