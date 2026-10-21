"""Generate provenance-checked RAGAS queries for a clustered PDF corpus.

Each document receives one single-document query. The output is RAGAS-compatible
JSONL with cluster and document provenance labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable


LOGGER = logging.getLogger("cluster_ragas")
DEFAULT_SOURCE_ROOT = Path("/Users/dc/united/pdfs")
DEFAULT_MANIFEST = Path(__file__).with_name("cluster_manifest.json")
DEFAULT_OUTPUT = Path(__file__).parent / "generated" / "cluster_ragas_queries.jsonl"
DEFAULT_PER_DOCUMENT_DIR = Path(__file__).parent / "generated" / "by_document"
MAX_PAGE_CHARACTERS = 2_000
MAX_DOCUMENT_CHARACTERS = 8_000


@dataclass(frozen=True)
class SourceSample:
    path: str
    cluster: str
    filename: str
    content_sha256: str
    page_contexts: tuple[dict[str, Any], ...]

    @property
    def context(self) -> str:
        return "\n\n".join(
            f"[PAGE {item['page']}]\n{item['text']}" for item in self.page_contexts
        )


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    documents = data.get("documents") or []
    if len(documents) != 50:
        raise ValueError(f"manifest must contain 50 documents, found {len(documents)}")
    paths = [item["path"] for item in documents]
    if len(paths) != len(set(paths)):
        raise ValueError("manifest contains duplicate paths")
    if any(not item.get("cluster") for item in documents):
        raise ValueError("every document must have a cluster label")
    return data


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _normalized_evidence_text(value: str) -> str:
    """Normalize Unicode and punctuation without permitting paraphrases."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _page_indices(page_count: int) -> list[int]:
    candidates = [0, 1, page_count // 2, page_count - 1]
    return list(dict.fromkeys(index for index in candidates if 0 <= index < page_count))


def sample_pdf(source_root: Path, entry: dict[str, str]) -> SourceSample:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required; install evals/requirements.txt") from exc

    relative = entry["path"]
    path = source_root / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    reader = PdfReader(path)
    contexts: list[dict[str, Any]] = []
    remaining = MAX_DOCUMENT_CHARACTERS
    for index in _page_indices(len(reader.pages)):
        text = _normalized_text(reader.pages[index].extract_text() or "")
        if not text:
            continue
        text = text[: min(MAX_PAGE_CHARACTERS, remaining)]
        contexts.append({"page": index + 1, "text": text})
        remaining -= len(text)
        if remaining <= 0:
            break
    if not contexts:
        raise ValueError(f"no extractable text in {path}")
    return SourceSample(
        path=relative,
        cluster=entry["cluster"],
        filename=path.name,
        content_sha256=digest,
        page_contexts=tuple(contexts),
    )


def _source_block(label: str, source: SourceSample) -> str:
    return (
        f"<source label=\"{label}\" filename=\"{source.filename}\" "
        f"path=\"{source.path}\">\n{source.context}\n</source>"
    )


def evidence_candidates(sources: list[SourceSample]) -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for source_index, source in enumerate(sources):
        label = chr(ord("A") + source_index)
        for passage_index, item in enumerate(source.page_contexts, start=1):
            candidate_id = f"{label}{passage_index}"
            candidates[candidate_id] = {
                "source_label": label,
                "page": item["page"],
                "quote": item["text"][:800],
            }
    return candidates


def generation_prompt(sources: list[SourceSample]) -> list[dict[str, str]]:
    labels = [chr(ord("A") + index) for index in range(len(sources))]
    source_text = "\n\n".join(
        _source_block(label, source) for label, source in zip(labels, sources)
    )
    if len(sources) != 1:
        raise ValueError("single-document generation requires exactly one source")
    candidates = evidence_candidates(sources)
    candidate_text = "\n\n".join(
        f"[EVIDENCE {candidate_id} | PAGE {item['page']}]\n{item['quote']}"
        for candidate_id, item in candidates.items()
    )
    requirement = (
        "The question and reference answer must be supported by source A. Select "
        "one or more evidence IDs that directly support the answer. The question must "
        "contain enough domain context to distinguish the source cluster from adjacent "
        "clusters. For research sources, identify that the requested result comes from "
        "a study, data analysis, or research report when the same wording could otherwise "
        "sound like clinical guidance or general population health."
    )
    return [
        {
            "role": "system",
            "content": (
                "You create rigorous retrieval evaluation records. Use only the "
                "provided sources. Do not use outside knowledge. Return JSON with "
                "keys question, reference_answer, and evidence_ids. evidence_ids is "
                "a list containing only IDs from the supplied EVIDENCE passages. "
                "Questions must be natural, answerable, specific, and must not "
                "mention source labels or evidence IDs."
            ),
        },
        {
            "role": "user",
            "content": f"{requirement}\n\n{source_text}\n\n{candidate_text}",
        },
    ]


def _quote_is_grounded(quote: str, source: SourceSample, page: int) -> bool:
    normalized_quote = _normalized_evidence_text(quote)
    if len(normalized_quote) < 12:
        return False
    return any(
        item["page"] == page
        and normalized_quote in _normalized_evidence_text(item["text"])
        for item in source.page_contexts
    )


def validate_generation(payload: dict[str, Any], sources: list[SourceSample]) -> None:
    if not isinstance(payload.get("question"), str) or not payload["question"].strip():
        raise ValueError("missing question")
    if not isinstance(payload.get("reference_answer"), str) or not payload["reference_answer"].strip():
        raise ValueError("missing reference_answer")
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("missing evidence")
    by_label = {chr(ord("A") + index): source for index, source in enumerate(sources)}
    observed: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError("evidence item is not an object")
        label = item.get("source_label")
        if label not in by_label:
            raise ValueError(f"unknown evidence source label {label!r}")
        try:
            page = int(item.get("page"))
        except (TypeError, ValueError) as exc:
            raise ValueError("evidence page is not an integer") from exc
        quote = item.get("quote")
        if not isinstance(quote, str) or not _quote_is_grounded(quote, by_label[label], page):
            raise ValueError(f"ungrounded evidence quote for source {label}")
        observed.add(label)
    if observed != set(by_label):
        raise ValueError(f"evidence must cover every source; observed {sorted(observed)}")


def generate_payload(
    client: Any,
    *,
    model: str,
    sources: list[SourceSample],
    max_retries: int,
) -> dict[str, Any]:
    error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=generation_prompt(sources),
            )
            payload = json.loads(response.choices[0].message.content)
            selected_ids = payload.pop("evidence_ids", None)
            candidates = evidence_candidates(sources)
            if not isinstance(selected_ids, list) or not selected_ids:
                raise ValueError("missing evidence_ids")
            if any(candidate_id not in candidates for candidate_id in selected_ids):
                raise ValueError(f"unknown evidence_ids: {selected_ids}")
            payload["evidence"] = [candidates[candidate_id] for candidate_id in selected_ids]
            validate_generation(payload, sources)
            return payload
        except Exception as exc:  # API and validation retries share one bound.
            error = exc
            LOGGER.warning(
                "generation attempt %d/%d failed for %s: %s",
                attempt,
                max_retries,
                [source.filename for source in sources],
                exc,
            )
            if attempt < max_retries:
                time.sleep(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"generation failed after {max_retries} attempts") from error


def make_record(
    *,
    record_id: str,
    kind: str,
    sources: list[SourceSample],
    payload: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    evidence = payload["evidence"]
    source_records = [
        {
            "label": chr(ord("A") + index),
            "path": source.path,
            "filename": source.filename,
            "content_sha256": source.content_sha256,
        }
        for index, source in enumerate(sources)
    ]
    evidence_labels = {item["source_label"] for item in evidence}
    return {
        "id": record_id,
        "kind": kind,
        "cluster": sources[0].cluster,
        "user_input": payload["question"].strip(),
        "reference": payload["reference_answer"].strip(),
        "reference_contexts": [source.context for source in sources],
        "source_documents": source_records,
        "source_document_count": len(sources),
        "combined_document_paths": [source.path for source in sources],
        "evidence": evidence,
        "all_sources_evidenced": evidence_labels
        == {record["label"] for record in source_records},
        "synthesizer_name": "controlled_single_document_llm",
        "generation_model": model,
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def per_document_output_path(root: Path, source_path: str) -> Path:
    """Map a source PDF path to a collision-resistant per-document output path."""
    relative = PurePosixPath(source_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"source path must be relative and traversal-free: {source_path!r}")
    if relative.suffix.casefold() == ".pdf":
        relative = relative.with_suffix("")
    return root.joinpath(*relative.parts) / "ragas.jsonl"


def write_per_document_files(
    root: Path,
    records: Iterable[dict[str, Any]],
) -> list[Path]:
    """Write exactly one RAGAS JSONL record under each source document path."""
    outputs: list[Path] = []
    seen_sources: set[str] = set()
    for record in records:
        sources = record.get("source_documents")
        if not isinstance(sources, list) or len(sources) != 1:
            raise ValueError(
                f"record {record.get('id')!r} must contain exactly one source document"
            )
        source_path = sources[0].get("path")
        if not isinstance(source_path, str) or not source_path:
            raise ValueError(f"record {record.get('id')!r} has no source path")
        if source_path in seen_sources:
            raise ValueError(f"duplicate source document in records: {source_path}")
        seen_sources.add(source_path)
        output = per_document_output_path(root, source_path)
        write_jsonl(output, [record])
        outputs.append(output)
    return outputs


def build_tasks(manifest: dict[str, Any], samples: dict[str, SourceSample]) -> list[tuple[str, str, list[SourceSample]]]:
    tasks: list[tuple[str, str, list[SourceSample]]] = []
    for index, entry in enumerate(manifest["documents"], start=1):
        tasks.append((f"single-{index:03d}", "single_document", [samples[entry["path"]]]))
    return tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--per-document-dir",
        type=Path,
        default=DEFAULT_PER_DOCUMENT_DIR,
        help="root directory for one ragas.jsonl file per source document",
    )
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    manifest = load_manifest(args.manifest)
    samples = {
        entry["path"]: sample_pdf(args.source_root, entry)
        for entry in manifest["documents"]
    }
    tasks = build_tasks(manifest, samples)
    duplicate_groups: dict[str, list[str]] = {}
    for source in samples.values():
        duplicate_groups.setdefault(source.content_sha256, []).append(source.path)
    duplicates = [paths for paths in duplicate_groups.values() if len(paths) > 1]
    LOGGER.info(
        "validated %d documents, %d clusters, %d tasks, %d duplicate groups",
        len(samples),
        len({sample.cluster for sample in samples.values()}),
        len(tasks),
        len(duplicates),
    )
    if args.dry_run:
        print(json.dumps({
            "documents": len(samples),
            "single_document_queries": len(manifest["documents"]),
            "total_queries": len(tasks),
            "duplicate_groups": duplicates,
        }, indent=2))
        return
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required unless --dry-run is used")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install evals/requirements.txt before generation") from exc
    client = OpenAI(timeout=60.0, max_retries=2)
    partial_path = args.output.with_suffix(".partial.jsonl")
    records = {
        record["id"]: record
        for record in read_jsonl(partial_path)
        if isinstance(record.get("id"), str)
    }
    pending_tasks = [task for task in tasks if task[0] not in records]
    if records:
        LOGGER.info("resuming with %d validated records", len(records))
    failures: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                generate_payload,
                client,
                model=args.model,
                sources=sources,
                max_retries=args.max_retries,
            ): (record_id, kind, sources)
            for record_id, kind, sources in pending_tasks
        }
        for future in as_completed(futures):
            record_id, kind, sources = futures[future]
            try:
                payload = future.result()
                records[record_id] = make_record(
                    record_id=record_id,
                    kind=kind,
                    sources=sources,
                    payload=payload,
                    model=args.model,
                )
                ordered_partial = [
                    records[item_id]
                    for item_id, _, _ in tasks
                    if item_id in records
                ]
                write_jsonl(partial_path, ordered_partial)
                LOGGER.info("generated %s (%d/%d)", record_id, len(records), len(tasks))
            except Exception as exc:
                failures[record_id] = str(exc)
                LOGGER.error("failed %s: %s", record_id, exc)
    if failures:
        raise RuntimeError(
            f"{len(failures)} query generations failed; "
            f"{len(records)} validated records saved to {partial_path}: {failures}"
        )
    ordered = [records[record_id] for record_id, _, _ in tasks]
    write_jsonl(args.output, ordered)
    per_document_outputs = write_per_document_files(args.per_document_dir, ordered)
    partial_path.unlink(missing_ok=True)
    print(f"Wrote {len(ordered)} RAGAS-compatible records to {args.output}")
    print(
        f"Wrote {len(per_document_outputs)} per-document files under "
        f"{args.per_document_dir}"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
