"""Table-aware Docling conversion for every coverage-policy PDF.

Same DocumentConverter + HybridChunker settings already validated on the
bendamustine policy in d1.py, looped over the whole folder. Skips PDFs that
already have a .docling.md next to them, so a killed/timed-out run can just
be re-invoked to pick up where it left off.
"""
from pathlib import Path
import time
import traceback

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)

POLICY_DIR = Path("/Users/dc/geha/downloads/coverage-policies")


def convert_one(converter, chunker, pdf_path: Path) -> int:
    document = converter.convert(pdf_path).document

    markdown = document.export_to_markdown()
    pdf_path.with_suffix(".docling.md").write_text(markdown, encoding="utf-8")

    chunks = list(chunker.chunk(document))
    chunk_path = pdf_path.with_suffix(".docling_chunks.md")
    with chunk_path.open("w", encoding="utf-8") as output:
        for number, chunk in enumerate(chunks, 1):
            text = chunker.contextualize(chunk)
            output.write(f"## Chunk {number}\n\n{text}\n\n\n\n")
    return len(chunks)


def main() -> None:
    pdfs = sorted(POLICY_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {POLICY_DIR}")

    todo = [p for p in pdfs if not p.with_suffix(".docling.md").exists()]
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
            n_chunks = convert_one(converter, chunker, pdf_path)
            elapsed = time.perf_counter() - started
            print(f"[{index}/{len(todo)}] {pdf_path.name}: {n_chunks} chunks in {elapsed:.1f}s")
        except Exception as exc:  # keep going; report at the end
            elapsed = time.perf_counter() - started
            print(f"[{index}/{len(todo)}] {pdf_path.name}: FAILED after {elapsed:.1f}s - {exc}")
            traceback.print_exc()
            failures.append(pdf_path.name)

    print(f"\nDone. {len(todo) - len(failures)}/{len(todo)} converted this run.")
    if failures:
        print("Failed:")
        for name in failures:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
