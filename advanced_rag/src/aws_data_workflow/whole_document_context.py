"""Summarize and embed a whole form/application without fragmenting it."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

from .contextual_embeddings import make_titan_embedder, read_jsonl, write_jsonl_atomic


SUMMARY_PROMPT_VERSION = "whole-form-summary-v1"
SUMMARY_SYSTEM_PROMPT = (
    "You summarize administrative forms and benefit applications for retrieval. "
    "Use only the supplied document. Preserve the form name, issuing organization, "
    "purpose, intended applicant, major sections, required information, and submission "
    "instructions. Do not fill in the form or infer missing facts."
)
SUMMARY_USER_PROMPT = """Summarize this complete form or application for search retrieval.

<document>
{document}
</document>

Return one concise factual summary. The complete source remains the authoritative evidence."""


Summarizer = Callable[[str], str]


def prepare_whole_document_directory(document_dir: Path) -> dict[str, Any]:
    """Build one complete source record from already extracted single-page files."""
    job_path = document_dir / "job.json"
    if not job_path.is_file():
        raise FileNotFoundError(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    selected_pages: list[str] = []
    page_sources: list[str] = []
    for page_dir in sorted((document_dir / "pages").glob("page-*")):
        candidates = (
            page_dir / "docling.normalized.md",
            page_dir / "llamaparse.md",
            page_dir / "deepseek.md",
            page_dir / "docling.md",
        )
        selected = next((path for path in candidates if path.is_file()), None)
        if selected is None:
            raise FileNotFoundError(f"No extracted Markdown found in {page_dir}")
        selected_pages.append(selected.read_text(encoding="utf-8").strip())
        page_sources.append(str(selected.relative_to(document_dir)))
    document_text = "\n\n".join(selected_pages).strip()
    if not document_text:
        raise ValueError(f"No extracted document text under {document_dir}")

    from .docling_chunking import (
        _document_id,
        build_whole_document_record,
        write_jsonl,
    )
    from .document_router import classify_document

    source = document_dir / job.get("sourceName", "source.pdf")
    classification = classify_document(job["filename"], document_text)
    if classification["route"] != "whole_document_context":
        raise ValueError(f"Document is not classified as a form/application: {job['filename']}")
    document_path = document_dir / "document.md"
    document_path.write_text(document_text + "\n", encoding="utf-8")
    records = build_whole_document_record(
        source=source,
        document_id=_document_id(source),
        text=document_text,
        classification=classification,
    )
    chunks_path = document_dir / "chunks.jsonl"
    write_jsonl(records, chunks_path)
    route_manifest = {
        "schema_version": "1.0",
        "document_id": job["id"],
        "filename": job["filename"],
        "route": classification["route"],
        "document_type": classification["document_type"],
        "storage_strategy": "whole_document",
        "pages": len(selected_pages),
        "page_sources": page_sources,
        "document_markdown": document_path.name,
        "records": len(records),
        "chunks": chunks_path.name,
    }
    (document_dir / "whole-document-route.json").write_text(
        json.dumps(route_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return route_manifest


def make_bedrock_whole_document_summarizer(
    model_id: str,
    *,
    region_name: str | None = None,
    client: Any | None = None,
) -> Summarizer:
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=region_name)

    def summarize(document: str) -> str:
        response = client.converse(
            modelId=model_id,
            system=[{"text": SUMMARY_SYSTEM_PROMPT}],
            messages=[{
                "role": "user",
                "content": [{"text": SUMMARY_USER_PROMPT.format(document=document)}],
            }],
            inferenceConfig={"maxTokens": 700, "temperature": 0},
        )
        return " ".join(
            block["text"]
            for block in response["output"]["message"]["content"]
            if block.get("text")
        ).strip()

    return summarize


def build_whole_document_context(
    *,
    record: dict[str, Any],
    summarize: Summarizer,
    embed_text: Callable[[str], list[float]],
    context_model: str,
    embedding_model: str,
) -> dict[str, Any]:
    if record.get("metadata", {}).get("storage_strategy") != "whole_document":
        raise ValueError("record is not routed as a whole document")
    document = str(record.get("text") or "").strip()
    if not document:
        raise ValueError("whole document text is empty")
    summary = " ".join(summarize(document).split()).strip()
    if not summary:
        raise RuntimeError("whole document summarizer returned empty text")
    vector = embed_text(summary)
    if not vector:
        raise RuntimeError("embedding model returned an empty vector")
    return {
        **record,
        "text": document,
        "retrieval_context": summary,
        "contextual_retrieval_text": summary,
        "embedding": vector,
        "embedding_dimensions": len(vector),
        "context_model": context_model,
        "embedding_model": embedding_model,
        "prompt_version": SUMMARY_PROMPT_VERSION,
    }


def contextualize_whole_document_file(
    *,
    chunks_path: Path,
    output_path: Path,
    context_model: str,
    embedding_model: str = "amazon.titan-embed-text-v2:0",
    dimensions: int = 1024,
    region_name: str | None = None,
) -> dict[str, Any]:
    records = read_jsonl(chunks_path)
    if len(records) != 1:
        raise ValueError("whole-document route requires exactly one record")
    enriched = build_whole_document_context(
        record=records[0],
        summarize=make_bedrock_whole_document_summarizer(
            context_model, region_name=region_name
        ),
        embed_text=make_titan_embedder(
            embedding_model, dimensions=dimensions, region_name=region_name
        ),
        context_model=context_model,
        embedding_model=embedding_model,
    )
    write_jsonl_atomic([enriched], output_path)
    return {
        "output": str(output_path),
        "records": 1,
        "storage_strategy": "whole_document",
        "context_model": context_model,
        "embedding_model": embedding_model,
        "embedding_dimensions": dimensions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--context-model", default=os.environ.get("BEDROCK_CONTEXT_MODEL_ID")
    )
    parser.add_argument(
        "--embedding-model", default="amazon.titan-embed-text-v2:0"
    )
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION"))
    args = parser.parse_args()
    if not args.context_model:
        parser.error("--context-model or BEDROCK_CONTEXT_MODEL_ID is required")
    result = contextualize_whole_document_file(
        chunks_path=args.chunks.expanduser().resolve(),
        output_path=args.output.expanduser().resolve(),
        context_model=args.context_model,
        embedding_model=args.embedding_model,
        dimensions=args.dimensions,
        region_name=args.region,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
