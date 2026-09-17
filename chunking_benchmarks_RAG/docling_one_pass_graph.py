"""One-pass, non-overwriting Docling extraction for a GEHA policy PDF.

The extraction node calls the original ``convert_one`` function used to make
the published ``.docling.md`` and ``.docling_chunks.md`` files. It runs on a
temporary PDF copy so an existing published artifact is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

try:
    from .convert_pdf_to_docling import POLICY_DIR, convert_one
except ImportError:  # direct script execution
    from convert_pdf_to_docling import POLICY_DIR, convert_one


class ExtractionState(TypedDict, total=False):
    pdf_filename: str
    run_dir: str
    staged_markdown: str
    staged_chunks: str
    chunk_count: int
    comparison: dict[str, dict[str, str | bool | None]]
    status: str


def _source_pdf(filename: str) -> Path:
    if not filename or Path(filename).name != filename or not filename.lower().endswith(".pdf"):
        raise ValueError("Supply one PDF filename, not a path")
    source = POLICY_DIR / filename
    if not source.is_file() or source.resolve().parent != POLICY_DIR.resolve():
        raise FileNotFoundError(f"Policy PDF not found: {filename}")
    return source


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_docling(state: ExtractionState) -> ExtractionState:
    """Run the same converter and ``convert_one`` call as the original job, once."""
    from docling.chunking import HybridChunker
    from docling.document_converter import DocumentConverter
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    source = _source_pdf(state["pdf_filename"])
    staged_pdf = Path(state["run_dir"]) / source.name
    shutil.copyfile(source, staged_pdf)
    converter = DocumentConverter()
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5", max_tokens=700
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    count = convert_one(converter, chunker, staged_pdf)
    return {
        "staged_markdown": str(staged_pdf.with_suffix(".docling.md")),
        "staged_chunks": str(staged_pdf.with_suffix(".docling_chunks.md")),
        "chunk_count": count,
    }


def verify_outputs(state: ExtractionState) -> ExtractionState:
    """Compare both new artifacts byte-for-byte with their published counterparts."""
    source = _source_pdf(state["pdf_filename"])
    comparison: dict[str, dict[str, str | bool | None]] = {}
    for suffix, staged_key in (
        (".docling.md", "staged_markdown"),
        (".docling_chunks.md", "staged_chunks"),
    ):
        saved = source.with_suffix(suffix)
        staged = Path(state[staged_key])
        comparison[suffix] = {
            "saved_path": str(saved),
            "saved_sha256": _sha256(saved) if saved.exists() else None,
            "staged_sha256": _sha256(staged),
            "matches": saved.read_bytes() == staged.read_bytes() if saved.exists() else None,
        }
    matches = [entry["matches"] for entry in comparison.values()]
    if matches == [True, True]:
        status = "matched_existing"
    elif matches == [None, None]:
        status = "new_artifacts"
    elif None in matches:
        status = "incomplete_existing_pair"
    else:
        status = "mismatch_existing"
    return {"comparison": comparison, "status": status}


def publish_new(state: ExtractionState) -> ExtractionState:
    """Publish only when neither output exists; exclusive create prevents overwrite."""
    paths = (
        (Path(state["staged_markdown"]), POLICY_DIR / Path(state["staged_markdown"]).name),
        (Path(state["staged_chunks"]), POLICY_DIR / Path(state["staged_chunks"]).name),
    )
    created: list[Path] = []
    try:
        for staged, target in paths:
            with target.open("xb") as output:
                created.append(target)
                output.write(staged.read_bytes())
    except Exception:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    return {"status": "published_new"}


def build_graph():
    graph = StateGraph(ExtractionState)
    graph.add_node("extract_docling", extract_docling)
    graph.add_node("verify_outputs", verify_outputs)
    graph.add_node("publish_new", publish_new)
    graph.add_edge(START, "extract_docling")
    graph.add_edge("extract_docling", "verify_outputs")
    graph.add_conditional_edges(
        "verify_outputs",
        lambda state: "publish_new" if state["status"] == "new_artifacts" else "end",
        {"publish_new": "publish_new", "end": END},
    )
    graph.add_edge("publish_new", END)
    return graph.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_filename", help="One PDF basename in downloads/coverage-policies")
    args = parser.parse_args()
    _source_pdf(args.pdf_filename)
    with tempfile.TemporaryDirectory(prefix="geha-docling-") as run_dir:
        initial_state: ExtractionState = {
            "pdf_filename": args.pdf_filename,
            "run_dir": run_dir,
        }
        graph = build_graph()
        result = graph.invoke(initial_state)
    print(json.dumps({
        "source_pdf": args.pdf_filename,
        "chunk_count": result["chunk_count"],
        "status": result["status"],
        "comparison": result["comparison"],
    }, indent=2))


if __name__ == "__main__":
    main()
