"""Resumable LLM judge for extracted chunks and Claude retrieval context."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict


JUDGE_MODEL = "claude-sonnet-5-5"
JUDGE_PROMPT_VERSION = "contextual-integrity-judge-v1"


class Judgment(TypedDict):
    verdict: Literal["pass", "review", "fail"]
    source_integrity: Literal["clean", "suspect", "corrupt"]
    context_grounding: Literal["grounded", "partially_grounded", "unsupported"]
    source_issues: list[str]
    context_issues: list[str]
    rationale: str
    confidence: float


JudgeGenerator = Callable[[str, str], Judgment]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(path)


def make_claude_judge(model: str = JUDGE_MODEL) -> JudgeGenerator:
    """Create a Claude tool-call judge with a constrained output schema."""
    import anthropic

    client = anthropic.Anthropic(max_retries=2, timeout=180)
    tool = {
        "name": "submit_integrity_judgment",
        "description": "Submit the quality judgment for one extracted page and its context.",
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "verdict",
                "source_integrity",
                "context_grounding",
                "source_issues",
                "context_issues",
                "rationale",
                "confidence",
            ],
            "properties": {
                "verdict": {"type": "string", "enum": ["pass", "review", "fail"]},
                "source_integrity": {"type": "string", "enum": ["clean", "suspect", "corrupt"]},
                "context_grounding": {"type": "string", "enum": ["grounded", "partially_grounded", "unsupported"]},
                "source_issues": {"type": "array", "items": {"type": "string"}},
                "context_issues": {"type": "array", "items": {"type": "string"}},
                "rationale": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
    }

    def generate(source: str, context: str) -> Judgment:
        response = client.messages.create(
            model=model,
            max_tokens=700,
            system=(
                "You are an independent retrieval-quality judge. Inspect the extracted "
                "page for obvious corruption such as gibberish, truncation, duplicated "
                "fragments, broken reading order, and synthetic table headers like 0/1/2. "
                "Then determine whether the supplied retrieval context is fully supported by "
                "the extracted page, introduces unsupported claims, or omits the page's "
                "identity. Do not assume the extraction matches the PDF pixels; this is a "
                "text-integrity and grounding check. Use fail for corrupt source text or "
                "unsupported context, review for ambiguity, and pass only when both are sound."
            ),
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{
                "role": "user",
                "content": (
                    f"<extracted_page>\n{source}\n</extracted_page>\n\n"
                    f"<claude_context>\n{context}\n</claude_context>"
                ),
            }],
        )
        block = next(
            (item for item in response.content if item.type == "tool_use"),
            None,
        )
        if block is None:
            raise RuntimeError("Judge returned no structured judgment")
        return block.input  # type: ignore[return-value]

    return generate


def _summary(
    *,
    status: str,
    document_id: str,
    model: str,
    inputs: list[dict[str, Any]],
    records: list[dict[str, Any]],
    current_page: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    completed = {int(record["page"]): record for record in records}
    pages = []
    for item in inputs:
        page = int(item["page"])
        record = completed.get(page)
        pages.append({
            "page": page,
            "status": "complete" if record else (
                "processing" if page == current_page else "pending"
            ),
            "verdict": record.get("verdict") if record else None,
            "source_integrity": record.get("source_integrity") if record else None,
            "context_grounding": record.get("context_grounding") if record else None,
            "source_issues": record.get("source_issues", []) if record else [],
            "context_issues": record.get("context_issues", []) if record else [],
            "rationale": record.get("rationale") if record else None,
            "confidence": record.get("confidence") if record else None,
        })
    counts = {name: sum(1 for record in records if record["verdict"] == name) for name in ("pass", "review", "fail")}
    return {
        "schema_version": "1.0",
        "status": status,
        "document_id": document_id,
        "model": model,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "total_pages": len(inputs),
        "completed_pages": len(records),
        "current_page": current_page,
        "error": error,
        "counts": counts,
        "pages": pages,
        "updated_at": utc_now(),
    }


def initial_judge_status(
    contextual_dir: Path,
    *,
    document_id: str,
    model: str = JUDGE_MODEL,
) -> dict[str, Any]:
    inputs = _read_jsonl(contextual_dir / "contextual-pages.jsonl")
    records = _read_jsonl(contextual_dir / "judge" / "judgments.jsonl")
    return _summary(
        status="idle",
        document_id=document_id,
        model=model,
        inputs=inputs,
        records=records,
    )


def judge_contextual_pages(
    *,
    document_id: str,
    contextual_dir: Path,
    model: str = JUDGE_MODEL,
    generate_judgment: JudgeGenerator | None = None,
) -> dict[str, Any]:
    inputs = _read_jsonl(contextual_dir / "contextual-pages.jsonl")
    if not inputs:
        raise ValueError("No contextualized pages are available to judge")
    judge_dir = contextual_dir / "judge"
    output_path = judge_dir / "judgments.jsonl"
    metadata_path = judge_dir / "status.json"
    previous = {int(item["page"]): item for item in _read_jsonl(output_path)}
    records: list[dict[str, Any]] = []
    generate = generate_judgment or make_claude_judge(model)

    for item in inputs:
        page = int(item["page"])
        source = str(item.get("text", "")).strip()
        context = str(item.get("retrieval_context", "")).strip()
        source_sha256 = _sha256(source)
        context_sha256 = _sha256(context)
        prior = previous.get(page)
        if (
            prior
            and prior.get("source_sha256") == source_sha256
            and prior.get("context_sha256") == context_sha256
            and prior.get("judge_model") == model
            and prior.get("judge_prompt_version") == JUDGE_PROMPT_VERSION
        ):
            records.append(prior)
        else:
            _write_json_atomic(
                metadata_path,
                _summary(
                    status="running",
                    document_id=document_id,
                    model=model,
                    inputs=inputs,
                    records=records,
                    current_page=page,
                ),
            )
            judgment = generate(source, context)
            records.append({
                "page": page,
                "chunk_id": item.get("chunk_id"),
                **judgment,
                "source_sha256": source_sha256,
                "context_sha256": context_sha256,
                "judge_model": model,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "judged_at": utc_now(),
            })
        _write_jsonl_atomic(output_path, records)
        _write_json_atomic(
            metadata_path,
            _summary(
                status="running",
                document_id=document_id,
                model=model,
                inputs=inputs,
                records=records,
            ),
        )

    complete = _summary(
        status="complete",
        document_id=document_id,
        model=model,
        inputs=inputs,
        records=records,
    )
    _write_json_atomic(metadata_path, complete)
    return complete


def read_judge_status(judge_dir: Path) -> dict[str, Any] | None:
    path = judge_dir / "status.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def read_judgment(judge_dir: Path, page_number: int) -> dict[str, Any] | None:
    return next(
        (item for item in _read_jsonl(judge_dir / "judgments.jsonl") if item.get("page") == page_number),
        None,
    )
