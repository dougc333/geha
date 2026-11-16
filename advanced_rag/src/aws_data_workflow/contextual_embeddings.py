"""Create document-aware retrieval text and contextual embeddings with Bedrock."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable, TypedDict

from geha_processing.io import atomic_jsonl, read_jsonl as _read_jsonl


PROMPT_VERSION = "contextual-retrieval-v2-cached-document-prefix"
SYSTEM_PROMPT = (
    "You prepare concise context for retrieval indexing. Use only the supplied "
    "document. Do not answer questions, add advice, or introduce facts absent "
    "from the document."
)
USER_TEMPLATE = """Here is the chunk to situate:
<chunk>
{chunk}
</chunk>

Give a short, succinct context that situates this chunk within the document for
search retrieval. Include the document subject and any policy code, entity,
section, population, or time period needed to disambiguate it. Return only the
context."""


class ContextResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_write_input_tokens: int


ContextGenerator = Callable[[str, str], str | ContextResult]
Embedder = Callable[[str], list[float]]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return _read_jsonl(path)


def write_jsonl_atomic(records: Iterable[dict[str, Any]], output: Path) -> int:
    return atomic_jsonl(output, records)


def make_bedrock_context_generator(
    model_id: str,
    *,
    region_name: str | None = None,
    client: Any | None = None,
) -> ContextGenerator:
    """Create a generator with a cacheable document prefix before the chunk."""
    if client is None:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=region_name)

    def generate(document: str, chunk: str) -> ContextResult:
        response = client.converse(
            modelId=model_id,
            # Bedrock processes tools -> system -> messages. The stable document
            # therefore precedes the changing chunk, with an explicit cache
            # checkpoint at the end of the reusable system prefix.
            system=[
                {"text": SYSTEM_PROMPT},
                {"text": f"<document>\n{document}\n</document>"},
                {"cachePoint": {"type": "default"}},
            ],
            messages=[{
                "role": "user",
                "content": [{
                    "text": USER_TEMPLATE.format(chunk=chunk)
                }],
            }],
            inferenceConfig={"maxTokens": 256, "temperature": 0},
        )
        blocks = response["output"]["message"]["content"]
        context = " ".join(
            block["text"] for block in blocks if block.get("text")
        ).strip()
        usage = response.get("usage", {})
        return {
            "context": context,
            "input_tokens": int(usage.get("inputTokens", 0)),
            "output_tokens": int(usage.get("outputTokens", 0)),
            "cache_read_input_tokens": int(usage.get("cacheReadInputTokens", 0)),
            "cache_write_input_tokens": int(usage.get("cacheWriteInputTokens", 0)),
        }

    return generate


def make_titan_embedder(
    model_id: str = "amazon.titan-embed-text-v2:0",
    *,
    dimensions: int = 1024,
    region_name: str | None = None,
) -> Embedder:
    """Create a normalized Amazon Titan Text Embeddings V2 adapter."""
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region_name)

    def embed(text: str) -> list[float]:
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": text,
                "dimensions": dimensions,
                "normalize": True,
            }),
        )
        payload = json.loads(response["body"].read())
        return [float(value) for value in payload["embedding"]]

    return embed


def build_contextual_embeddings(
    *,
    document: str,
    chunks: Iterable[dict[str, Any]],
    generate_context: ContextGenerator,
    embed_text: Embedder,
    context_model: str,
    embedding_model: str,
    existing: dict[str, dict[str, Any]] | None = None,
    checkpoint: Callable[[list[dict[str, Any]]], None] | None = None,
) -> list[dict[str, Any]]:
    """Enrich chunks while retaining the original evidence text unchanged."""
    if not document.strip():
        raise ValueError("document text is empty")
    completed = existing or {}
    output: list[dict[str, Any]] = []

    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        prior = completed.get(chunk_id)
        if (
            prior
            and prior.get("text") == chunk.get("text")
            and prior.get("context_model") == context_model
            and prior.get("embedding_model") == embedding_model
            and prior.get("prompt_version") == PROMPT_VERSION
            and isinstance(prior.get("embedding"), list)
        ):
            record = prior
        else:
            generated = generate_context(document, chunk["text"])
            if isinstance(generated, str):
                raw_context = generated
                usage = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                }
            else:
                raw_context = generated["context"]
                usage = {
                    key: int(generated.get(key, 0))
                    for key in (
                        "input_tokens",
                        "output_tokens",
                        "cache_read_input_tokens",
                        "cache_write_input_tokens",
                    )
                }
            context = " ".join(raw_context.split()).strip()
            if not context:
                raise RuntimeError(f"empty retrieval context for {chunk_id}")
            contextual_text = f"{context}\n\n{chunk['text']}"
            vector = embed_text(contextual_text)
            if not vector:
                raise RuntimeError(f"empty embedding for {chunk_id}")
            record = {
                **chunk,
                "retrieval_context": context,
                "contextual_retrieval_text": contextual_text,
                "embedding": vector,
                "embedding_dimensions": len(vector),
                "context_model": context_model,
                "embedding_model": embedding_model,
                "prompt_version": PROMPT_VERSION,
                "prompt_cache": usage,
            }
        output.append(record)
        if checkpoint:
            checkpoint(output)
    return output


def contextualize_file(
    *,
    document_path: Path,
    chunks_path: Path,
    output_path: Path,
    context_model: str,
    embedding_model: str = "amazon.titan-embed-text-v2:0",
    dimensions: int = 1024,
    region_name: str | None = None,
) -> dict[str, Any]:
    document = document_path.read_text(encoding="utf-8")
    chunks = read_jsonl(chunks_path)
    previous = (
        {record["chunk_id"]: record for record in read_jsonl(output_path)}
        if output_path.exists()
        else {}
    )
    generator = make_bedrock_context_generator(
        context_model, region_name=region_name
    )
    embedder = make_titan_embedder(
        embedding_model,
        dimensions=dimensions,
        region_name=region_name,
    )
    records = build_contextual_embeddings(
        document=document,
        chunks=chunks,
        generate_context=generator,
        embed_text=embedder,
        context_model=context_model,
        embedding_model=embedding_model,
        existing=previous,
        checkpoint=lambda current: write_jsonl_atomic(current, output_path),
    )
    return {
        "document": str(document_path),
        "chunks": str(chunks_path),
        "output": str(output_path),
        "records": len(records),
        "context_model": context_model,
        "embedding_model": embedding_model,
        "embedding_dimensions": dimensions,
        "cache_read_input_tokens": sum(
            record.get("prompt_cache", {}).get("cache_read_input_tokens", 0)
            for record in records
        ),
        "cache_write_input_tokens": sum(
            record.get("prompt_cache", {}).get("cache_write_input_tokens", 0)
            for record in records
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--context-model",
        default=os.environ.get("BEDROCK_CONTEXT_MODEL_ID"),
        help="Bedrock model ID; may also be set with BEDROCK_CONTEXT_MODEL_ID",
    )
    parser.add_argument(
        "--embedding-model", default="amazon.titan-embed-text-v2:0"
    )
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION"))
    args = parser.parse_args()
    if not args.context_model:
        parser.error("--context-model or BEDROCK_CONTEXT_MODEL_ID is required")

    result = contextualize_file(
        document_path=args.document.expanduser().resolve(),
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

