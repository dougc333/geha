from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)

POLICY_DIR = Path("/Users/dc/geha/downloads/coverage-policies")
PDF_PATH = POLICY_DIR / "geha-coverage-policy-bendamustine.pdf"


def main() -> None:
    pdfs = sorted(POLICY_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {POLICY_DIR}")

    if not PDF_PATH.exists():
        raise FileNotFoundError(PDF_PATH)

    print(f"Converting {PDF_PATH.name}")

    converter = DocumentConverter()
    document = converter.convert(PDF_PATH).document

    markdown = document.export_to_markdown()
    markdown_path = PDF_PATH.with_suffix(".docling.md")
    markdown_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown saved to {markdown_path}")

    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5",
        max_tokens=700,
    )

    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
    )

    chunks = list(chunker.chunk(document))
    print(f"Created {len(chunks)} chunks")

    chunk_path = PDF_PATH.with_suffix(".docling_chunks.md")
    with chunk_path.open("w", encoding="utf-8") as output:
        for number, chunk in enumerate(chunks, 1):
            text = chunker.contextualize(chunk)
            output.write(f"## Chunk {number}\n\n{text}\n\n\n\n")

    print(f"Chunks saved to {chunk_path}")


if __name__ == "__main__":
    main()
