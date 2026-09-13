from pathlib import Path

from docling.document_converter import DocumentConverter


POLICY_DIR = Path("/Users/dc/geha/downloads/coverage-policies")


def main() -> None:
    pdfs = sorted(POLICY_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {POLICY_DIR}")
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in {POLICY_DIR}")

    pdf_path = pdfs[0]
    print(f"Converting {pdf_path.name}")
    result = DocumentConverter().convert(pdf_path)
    print(result.document.export_to_markdown())


if __name__ == "__main__":
    main()


# from docling.document_converter import DocumentConverter
# from docling.chunking import HybridChunker
# from transformers import AutoTokenizer

# pdf_path = "geha-coverage-policy-bendamustine.pdf"

# document = DocumentConverter().convert(pdf_path).document

# tokenizer = AutoTokenizer.from_pretrained(
#     "BAAI/bge-small-en-v1.5"
# )

# chunker = HybridChunker(
#     tokenizer=tokenizer,
#     max_tokens=700,
#     merge_peers=True,
# )

# chunks = list(chunker.chunk(document))

# for number, chunk in enumerate(chunks, 1):
#     text = chunker.contextualize(chunk)

#     print(f"--- chunk {number} ---")
#     print(text)
