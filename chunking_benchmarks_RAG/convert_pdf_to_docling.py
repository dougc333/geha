"""Table-aware Docling conversion for every coverage-policy PDF.

Same DocumentConverter + HybridChunker settings already validated on the
bendamustine policy in d1.py, looped over the whole folder. Reads PDFs from
crawl_dir/raw/coverage-policies and writes each policy's outputs to its own
crawl_dir/verified/coverage-policies/<stem>/ folder. Skips PDFs that already
have a .docling.md there, so a killed/timed-out run can just be re-invoked to
pick up where it left off.
"""

from pathlib import Path
import time
import traceback

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)

try:
    from .policy_paths import POLICY_ARTIFACT_DIR, POLICY_PDF_DIR
except ImportError:  # direct script execution
    from policy_paths import POLICY_ARTIFACT_DIR, POLICY_PDF_DIR

POLICY_DIR = POLICY_PDF_DIR


def artifact_dir(pdf_path: Path) -> Path:
    """Return the verified-corpus folder that holds one policy's Docling outputs."""
    return POLICY_ARTIFACT_DIR / pdf_path.stem


def convert_one(converter, chunker, pdf_path: Path, output_dir: Path | None = None) -> int:
    """Write ``<stem>.docling.md`` and ``<stem>.docling_chunks.md`` (next to the PDF by default)."""
    output_dir = output_dir or pdf_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    document = converter.convert(pdf_path).document

    markdown = document.export_to_markdown()
    (output_dir / f"{pdf_path.stem}.docling.md").write_text(markdown, encoding="utf-8")

    chunks = list(chunker.chunk(document))
    chunk_path = output_dir / f"{pdf_path.stem}.docling_chunks.md"
    with chunk_path.open("w", encoding="utf-8") as output:
        for number, chunk in enumerate(chunks, 1):
            text = chunker.contextualize(chunk)
            output.write(f"## Chunk {number}\n\n{text}\n\n\n\n")
    return len(chunks)


def main() -> None:
    pdfs = sorted(POLICY_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {POLICY_DIR}")

    todo = [p for p in pdfs if not (artifact_dir(p) / f"{p.stem}.docling.md").exists()]
    print(f"{len(pdfs) - len(todo)} already converted, {len(todo)} remaining")

    if not todo:
        return

    converter = DocumentConverter()
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5",
        max_tokens=700,
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

    failures = []
    for index, pdf_path in enumerate(todo, 1):
        started = time.perf_counter()
        try:
            n_chunks = convert_one(converter, chunker, pdf_path, artifact_dir(pdf_path))
            elapsed = time.perf_counter() - started
            print(
                f"[{index}/{len(todo)}] {pdf_path.name}: {n_chunks} chunks in {elapsed:.1f}s"
            )
        except Exception as exc:  # keep going; report at the end
            elapsed = time.perf_counter() - started
            print(
                f"[{index}/{len(todo)}] {pdf_path.name}: FAILED after {elapsed:.1f}s - {exc}"
            )
            traceback.print_exc()
            failures.append(pdf_path.name)

    print(f"\nDone. {len(todo) - len(failures)}/{len(todo)} converted this run.")
    if failures:
        print("Failed:")
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
