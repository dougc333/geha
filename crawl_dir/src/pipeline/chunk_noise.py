"""Chunk length and noise statistics for processed runs.

The noise flags are text heuristics, not labels: they estimate how much of a
corpus is table-of-contents pages, fill-in form fields, short fragments and
template boilerplate shared across documents.
"""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

TINY_WORDS = 25
TOC_MIN_MATCHES = 3
FORM_MIN_MATCHES = 2
BOILERPLATE_LINE_SHARE = 0.5
BOILERPLATE_MIN_DOCS = 5
BOILERPLATE_DOC_FRACTION = 0.1

WORD_RE = re.compile(r"\w+")
DIGITS_RE = re.compile(r"\d+")
# Dot leaders followed by a page number, or a line ending in a page number after wide spacing.
TOC_RE = re.compile(r"\.{5,}\s*\d+|\s{2,}\d+\s*$", re.M)
FORM_RE = re.compile(
    r"_{4,}|☐|□|\[\s\]|(signature|date of birth|member id|ssn)\s*:?\s*$",
    re.I | re.M,
)
NOISE_FLAGS = ("toc", "form", "tiny", "boilerplate")
LENGTH_BUCKETS = ((1, 2), (3, 5), (6, 15), (16, 40), (41, None))


@dataclass
class DocumentStats:
    document_id: str
    family: str
    run_id: str
    pages: int
    chunks: int
    median_words: float
    p90_words: float
    toc: int
    form: int
    tiny: int
    boilerplate: int
    table: int


def normalize_line(line: str) -> str:
    """Lowercase a line and mask digits so dates and page numbers compare equal."""
    return DIGITS_RE.sub("#", line.strip().lower())


def template_lines(texts: Iterable[str]) -> set[str]:
    lines = set()
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            if 8 <= len(line) <= 120:
                lines.add(normalize_line(line))
    return lines


def is_toc(text: str) -> bool:
    return len(TOC_RE.findall(text)) >= TOC_MIN_MATCHES


def is_form(text: str) -> bool:
    return len(FORM_RE.findall(text)) >= FORM_MIN_MATCHES


def is_tiny(text: str) -> bool:
    return len(WORD_RE.findall(text)) < TINY_WORDS


def boilerplate_share(text: str, boilerplate: set[str]) -> float:
    lines = [normalize_line(line) for line in text.splitlines() if line.strip()]
    if not lines:
        return 0.0
    return sum(line in boilerplate for line in lines) / len(lines)


def find_runs(runs_root: Path, batch: str | None = None) -> dict[str, Path]:
    """Pick one run directory per document: the named batch, else the newest."""
    selected: dict[str, tuple[str, Path]] = {}
    for chunks_path in sorted(runs_root.glob("*/*/*/candidate/chunks.jsonl")):
        run_dir = chunks_path.parents[1]
        if batch and run_dir.name != batch:
            continue
        manifest = run_dir / "run-manifest.json"
        created = ""
        if manifest.is_file():
            created = json.loads(manifest.read_text(encoding="utf-8")).get("created_at", "")
        key = f"{run_dir.parents[1].name}/{run_dir.parent.name}"
        if key not in selected or created > selected[key][0]:
            selected[key] = (created, run_dir)
    return {key: run_dir for key, (_, run_dir) in selected.items()}


def read_chunks(run_dir: Path) -> list[dict]:
    path = run_dir / "candidate" / "chunks.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, int(q * len(ordered)))])


def document_stats(
    run_dir: Path, chunks: list[dict], boilerplate: set[str]
) -> DocumentStats:
    lengths = [len(WORD_RE.findall(chunk["text"])) for chunk in chunks]
    pages = max((page for chunk in chunks for page in chunk.get("pages") or [0]), default=0)
    return DocumentStats(
        document_id=run_dir.parent.name,
        family=run_dir.parents[1].name,
        run_id=run_dir.name,
        pages=pages,
        chunks=len(chunks),
        median_words=float(statistics.median(lengths)) if lengths else 0.0,
        p90_words=percentile(lengths, 0.9),
        toc=sum(is_toc(chunk["text"]) for chunk in chunks),
        form=sum(is_form(chunk["text"]) for chunk in chunks),
        tiny=sum(is_tiny(chunk["text"]) for chunk in chunks),
        boilerplate=sum(
            boilerplate_share(chunk["text"], boilerplate) >= BOILERPLATE_LINE_SHARE
            for chunk in chunks
        ),
        table=sum(
            chunk.get("content_type") == "table" or bool(chunk.get("table_ids"))
            for chunk in chunks
        ),
    )


def group_summary(name: str, rows: list[DocumentStats]) -> dict:
    chunks = sum(row.chunks for row in rows)
    pages = sum(row.pages for row in rows)
    summary = {
        "group": name,
        "documents": len(rows),
        "pages": pages,
        "chunks": chunks,
        "chunks_per_page": round(chunks / pages, 2) if pages else None,
        "median_of_median_words": statistics.median(row.median_words for row in rows) if rows else 0,
    }
    for flag in NOISE_FLAGS + ("table",):
        count = sum(getattr(row, flag) for row in rows)
        summary[f"{flag}_chunks"] = count
        summary[f"{flag}_pct"] = round(100 * count / chunks, 1) if chunks else 0.0
        summary[f"{flag}_documents"] = sum(1 for row in rows if getattr(row, flag))
    return summary


def loglog_slope(points: list[tuple[float, float]]) -> float | None:
    points = [(x, y) for x, y in points if x > 0 and y > 0]
    if len(points) < 2:
        return None
    xs = [math.log(x) for x, _ in points]
    ys = [math.log(y) for _, y in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if not denominator:
        return None
    return round(sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator, 2)


def build_report(runs_root: Path, batch: str | None = None) -> dict:
    runs = find_runs(runs_root, batch)
    chunks_by_run = {key: read_chunks(run_dir) for key, run_dir in runs.items()}
    line_documents: Counter[str] = Counter()
    for chunks in chunks_by_run.values():
        line_documents.update(template_lines(chunk["text"] for chunk in chunks))
    threshold = max(BOILERPLATE_MIN_DOCS, BOILERPLATE_DOC_FRACTION * len(runs))
    boilerplate = {line for line, count in line_documents.items() if count >= threshold}

    rows = [
        document_stats(runs[key], chunks_by_run[key], boilerplate)
        for key in sorted(runs)
    ]
    families = sorted({row.family for row in rows})
    buckets = []
    for low, high in LENGTH_BUCKETS:
        members = [row for row in rows if row.pages >= low and (high is None or row.pages <= high)]
        if members:
            buckets.append(group_summary(f"{low}-{high or ''} pages", members))

    by_size = sorted(rows, key=lambda row: -row.chunks)
    total_chunks = sum(row.chunks for row in rows)
    frequencies = sorted(line_documents.values(), reverse=True)[:200]
    return {
        "runs_root": str(runs_root),
        "batch": batch,
        "boilerplate_min_documents": threshold,
        "corpus": group_summary("all", rows),
        "families": [group_summary(family, [r for r in rows if r.family == family]) for family in families],
        "length_buckets": buckets,
        "concentration": {
            f"top_{k}_documents_chunk_share_pct": round(
                100 * sum(row.chunks for row in by_size[:k]) / total_chunks, 1
            )
            for k in (1, 3, 5, 10)
        } if total_chunks else {},
        "chunks_vs_pages_exponent": loglog_slope([(row.pages, row.chunks) for row in rows]),
        "repeated_line_rank_frequency_slope": loglog_slope(
            [(rank, count) for rank, count in enumerate(frequencies, start=1)]
        ),
        "most_repeated_lines": [
            {"line": line, "documents": count} for line, count in line_documents.most_common(15)
        ],
        "documents": [asdict(row) for row in rows],
    }


STATS_FILENAME = "chunk-noise.json"


def list_runs(runs_root: Path) -> list[dict]:
    """Every run directory that has chunks, newest first."""
    runs = []
    for chunks_path in runs_root.glob("*/*/*/candidate/chunks.jsonl"):
        run_dir = chunks_path.parents[1]
        manifest = run_dir / "run-manifest.json"
        created = ""
        if manifest.is_file():
            created = json.loads(manifest.read_text(encoding="utf-8")).get("created_at", "")
        runs.append({
            "id": run_dir.relative_to(runs_root).as_posix(),
            "family": run_dir.parents[1].name,
            "document_id": run_dir.parent.name,
            "run_id": run_dir.name,
            "created_at": created,
        })
    return sorted(runs, key=lambda run: (run["created_at"], run["id"]), reverse=True)


def resolve_run(runs_root: Path, run_id: str) -> Path:
    """Map a ``family/document/run`` id to its directory, refusing paths outside runs_root."""
    root = runs_root.resolve()
    run_dir = (root / run_id).resolve()
    if run_dir.parent.parent.parent != root or not (run_dir / "candidate" / "chunks.jsonl").is_file():
        raise ValueError(f"Unknown run: {run_id}")
    return run_dir


def stats_path(stats_root: Path, runs_root: Path, run_dir: Path) -> Path:
    """Stats live under stats_root at the same family/document/run path as the run."""
    return stats_root / run_dir.relative_to(runs_root.resolve()) / STATS_FILENAME


def corpus_boilerplate(runs_root: Path) -> tuple[set[str], float]:
    """Template lines shared across the newest run of every document."""
    runs = find_runs(runs_root)
    line_documents: Counter[str] = Counter()
    for run_dir in runs.values():
        line_documents.update(template_lines(chunk["text"] for chunk in read_chunks(run_dir)))
    threshold = max(BOILERPLATE_MIN_DOCS, BOILERPLATE_DOC_FRACTION * len(runs))
    return {line for line, count in line_documents.items() if count >= threshold}, threshold


def chunk_rows(chunks: list[dict], boilerplate: set[str]) -> list[dict]:
    rows = []
    for chunk in chunks:
        text = chunk["text"]
        share = boilerplate_share(text, boilerplate)
        rows.append({
            "chunk_id": chunk.get("chunk_id", ""),
            "pages": chunk.get("pages") or [],
            "section": chunk.get("section") or "",
            "content_type": chunk.get("content_type") or "",
            "words": len(WORD_RE.findall(text)),
            "toc": is_toc(text),
            "form": is_form(text),
            "tiny": is_tiny(text),
            "boilerplate": share >= BOILERPLATE_LINE_SHARE,
            "boilerplate_share": round(share, 2),
            "table": chunk.get("content_type") == "table" or bool(chunk.get("table_ids")),
            "preview": " ".join(text.split())[:240],
        })
    return rows


def compute_run_stats(runs_root: Path, stats_root: Path, run_id: str) -> dict:
    """Compute stats for one run and save them next to its mirrored path under stats_root."""
    run_dir = resolve_run(runs_root, run_id)
    boilerplate, threshold = corpus_boilerplate(runs_root)
    chunks = read_chunks(run_dir)
    payload = {
        "schema_version": 1,
        "run": run_id,
        "computed_at": datetime.now(UTC).isoformat(),
        "heuristics": {
            "tiny_words": TINY_WORDS,
            "toc_min_matches": TOC_MIN_MATCHES,
            "form_min_matches": FORM_MIN_MATCHES,
            "boilerplate_line_share": BOILERPLATE_LINE_SHARE,
            "boilerplate_min_documents": threshold,
        },
        "summary": asdict(document_stats(run_dir, chunks, boilerplate)),
        "chunks": chunk_rows(chunks, boilerplate),
    }
    path = stats_path(stats_root, runs_root, run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique temporary file per call, so concurrent recomputes never share one.
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, indent=2) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def load_run_stats(runs_root: Path, stats_root: Path, run_id: str) -> dict | None:
    """Return saved stats for a run without recomputing, or None if none are saved."""
    path = stats_path(stats_root, runs_root, resolve_run(runs_root, run_id))
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
