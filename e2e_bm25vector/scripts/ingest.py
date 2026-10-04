#!/usr/bin/env python3
"""Extract, chunk, embed, and load one or more PDFs into the demo database."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import pymupdf
import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector

# Direct script execution places ``scripts/`` rather than the project root on
# sys.path. Add the root explicitly so the documented command works anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_core import chunk_text


def extract_chunks(pdf_path: Path) -> list[tuple[int, str]]:
    chunks: list[tuple[int, str]] = []
    with pymupdf.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            text = " ".join(page.get_text("text").split())
            chunks.extend((page_number, chunk) for chunk in chunk_text(text))
    return chunks


def ingest(pdf_path: Path, title: str | None = None) -> str:
    database_url = os.environ["DATABASE_URL"]
    document_id = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    chunks = extract_chunks(pdf_path)
    if not chunks:
        raise ValueError(f"No extractable text in {pdf_path}")

    embeddings = OpenAI().embeddings.create(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        input=[text for _, text in chunks],
    ).data

    with psycopg.connect(database_url) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rag_documents (id, title, source)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, source = EXCLUDED.source""",
                (document_id, title or pdf_path.stem, pdf_path.name),
            )
            cursor.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))
            cursor.executemany(
                """INSERT INTO rag_chunks
                   (document_id, chunk_index, page_number, content, embedding)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (document_id, index, page, text, embeddings[index].embedding)
                    for index, (page, text) in enumerate(chunks)
                ],
            )
    return document_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", nargs="+", type=Path)
    parser.add_argument("--title", help="Title override; valid only with one PDF")
    args = parser.parse_args()
    if args.title and len(args.pdf) != 1:
        parser.error("--title requires exactly one PDF")
    for path in args.pdf:
        print(path, ingest(path, args.title))


if __name__ == "__main__":
    main()
