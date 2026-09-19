"""Plain-text PDF chunking and local Chroma indexing for GEHA policies."""

from __future__ import annotations

import argparse
from pathlib import Path

import chromadb
import pdfplumber

ROOT = Path(__file__).resolve().parent
DEFAULT_PDF_DIR = ROOT.parent / "downloads" / "coverage-policies"
DEFAULT_DB_DIR = ROOT / ".chroma"
COLLECTION_NAME = "geha_plain_chunks_v1"
CHUNK_WORDS = 180
OVERLAP_WORDS = 30
BATCH_SIZE = 100


def split_page(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Make fixed-size, overlapping word chunks with no table handling."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + size]))
        if start + size >= len(words):
            break
    return chunks


def collect_chunks(pdf_dir: Path) -> tuple[list[dict], int, int, list[dict]]:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {pdf_dir}")

    chunks = []
    page_count = 0
    skipped_pages = []
    for pdf_path in pdfs:
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_count += 1
                # Reading-order text only: no table detection or row reconstruction.
                text = page.extract_text() or ""
                if not text.strip():
                    skipped_pages.append({"source_file": pdf_path.name, "page": page_number})
                    continue
                page_chunks = split_page(text)
                for chunk_number, chunk_text in enumerate(page_chunks, start=1):
                    chunks.append(
                        {
                            "id": f"{pdf_path.stem}-p{page_number}-c{chunk_number}",
                            "text": chunk_text,
                            "metadata": {
                                "source_file": pdf_path.name,
                                "page": page_number,
                                "chunk": chunk_number,
                            },
                        }
                    )
    if not chunks:
        raise ValueError("The PDFs contained no embedded text to index.")
    return chunks, len(pdfs), page_count, skipped_pages


def build_index(pdf_dir: Path = DEFAULT_PDF_DIR, db_dir: Path = DEFAULT_DB_DIR) -> dict:
    pdf_dir = Path(pdf_dir).expanduser().resolve()
    db_dir = Path(db_dir).expanduser().resolve()
    chunks, pdfs, pages, skipped_pages = collect_chunks(pdf_dir)
    client = chromadb.PersistentClient(path=str(db_dir))
    if COLLECTION_NAME in {collection.name for collection in client.list_collections()}:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME)
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        # Chroma's default embedding function embeds each plain-text chunk.
        collection.add(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["text"] for chunk in batch],
            metadatas=[chunk["metadata"] for chunk in batch],
        )
    return {
        "pdfs": pdfs,
        "indexed_pdfs": len({chunk["metadata"]["source_file"] for chunk in chunks}),
        "pages": pages,
        "indexed_pages": pages - len(skipped_pages),
        "skipped_pages": skipped_pages,
        "chunks": collection.count(),
        "db_dir": str(db_dir),
    }


def open_index(db_dir: Path = DEFAULT_DB_DIR):
    client = chromadb.PersistentClient(path=str(db_dir))
    return client.get_collection(COLLECTION_NAME)


def search(collection, question: str, k: int = 4, source_file: str | None = None) -> list[dict]:
    if not question.strip() or collection.count() == 0:
        return []
    args = {
        "query_texts": [question.strip()],
        "n_results": min(k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if source_file:
        args["where"] = {"source_file": source_file}
    result = collection.query(**args)
    return [
        {"id": chunk_id, "text": text, "metadata": metadata, "distance": distance}
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index GEHA PDFs as plain text chunks in Chroma")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    args = parser.parse_args()
    summary = build_index(args.pdf_dir, args.db_dir)
    print(
        f"Indexed {summary['indexed_pdfs']}/{summary['pdfs']} PDFs, "
        f"{summary['indexed_pages']}/{summary['pages']} pages, "
        f"{summary['chunks']} chunks into {summary['db_dir']}."
    )
    if summary["skipped_pages"]:
        print("Skipped pages without embedded text (OCR disabled):")
        for item in summary["skipped_pages"]:
            print(f"  {item['source_file']} page {item['page']}")
