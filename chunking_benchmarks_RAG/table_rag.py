"""Parent-child RAG over tables extracted from GEHA coverage policies."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from openai import AuthenticationError, OpenAI, PermissionDeniedError
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from sentence_transformers import SentenceTransformer


DEFAULT_DATABASE_URL = "postgresql://geha:geha-local@127.0.0.1:5433/geha_rag"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
CSV_SUFFIX = "_table_openai.csv"


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_tables (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    table_number integer NOT NULL,
    title text NOT NULL,
    full_csv text NOT NULL,
    rows_json jsonb NOT NULL,
    UNIQUE (source, table_number)
);

CREATE TABLE IF NOT EXISTS policy_table_vectors (
    id bigserial PRIMARY KEY,
    table_id bigint NOT NULL REFERENCES policy_tables(id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    search_text text NOT NULL,
    embedding vector(384) NOT NULL,
    UNIQUE (table_id, row_number)
);

CREATE INDEX IF NOT EXISTS policy_table_vectors_embedding_hnsw
ON policy_table_vectors USING hnsw (embedding vector_cosine_ops);
"""


def is_blank_row(row: list[str]) -> bool:
    return not row or all(not cell.strip() for cell in row)


def split_csv_tables(path: Path) -> list[list[list[str]]]:
    """Split a combined CSV on two consecutive empty records."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    blank_count = 0

    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.reader(stream):
            if is_blank_row(row):
                blank_count += 1
                if blank_count == 2 and current:
                    tables.append(current)
                    current = []
                    blank_count = 0
                continue

            blank_count = 0
            current.append(row)

    if current:
        tables.append(current)
    return tables


def normalized_table(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    width = max((len(row) for row in rows), default=0)
    if width == 0:
        return [], []
    padded = [row + [""] * (width - len(row)) for row in rows]
    headers = [
        cell.strip() or f"column_{index + 1}" for index, cell in enumerate(padded[0])
    ]
    return headers, padded[1:]


def infer_title(headers: list[str]) -> str:
    names = {header.casefold() for header in headers}
    if {"preference", "drug name"}.issubset(names):
        return "Drug preference and prior authorization"
    if {"drug name", "hcpcs code"}.issubset(names):
        return "Billing codes"
    if {"date", "updates"}.issubset(names):
        return "Revision history"
    return " / ".join(headers)


def table_as_csv(headers: list[str], rows: list[list[str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def table_as_records(headers: list[str], rows: list[list[str]]) -> list[dict[str, str]]:
    return [dict(zip(headers, row, strict=True)) for row in rows]


def row_search_text(source: str, title: str, headers: list[str], row: list[str]) -> str:
    values = "; ".join(
        f"{header}: {value}"
        for header, value in zip(headers, row, strict=True)
        if value.strip()
    )
    return f"Source: {source}\nTable: {title}\n{values}"


def connect(database_url: str):
    connection = psycopg.connect(database_url, row_factory=dict_row)
    register_vector(connection)
    return connection


def initialize_database(database_url: str) -> None:
    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(SCHEMA_SQL)
    print("Database schema is ready.")


def load_embedding_model(model_name: str) -> SentenceTransformer:
    model = SentenceTransformer(model_name)
    dimension = model.get_embedding_dimension()
    if dimension != 384:
        raise ValueError(
            f"Database schema expects 384-dimensional embeddings; {model_name} produces {dimension}."
        )
    return model


def ingest(
    database_url: str,
    input_dir: Path,
    embedding_model: SentenceTransformer,
) -> None:
    csv_paths = sorted(input_dir.glob(f"*{CSV_SUFFIX}"))
    if not csv_paths:
        raise FileNotFoundError(f"No *{CSV_SUFFIX} files found in {input_dir}")

    table_count = 0
    row_count = 0
    with connect(database_url) as connection:
        for csv_path in csv_paths:
            source = f"{csv_path.name.removesuffix(CSV_SUFFIX)}.pdf"
            tables = split_csv_tables(csv_path)
            print(f"{source}: {len(tables)} table(s)", flush=True)

            for table_number, raw_table in enumerate(tables, 1):
                headers, rows = normalized_table(raw_table)
                if not headers:
                    continue
                title = infer_title(headers)
                full_csv = table_as_csv(headers, rows)
                records = table_as_records(headers, rows)

                table_id = connection.execute(
                    """
                    INSERT INTO policy_tables
                        (source, table_number, title, full_csv, rows_json)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (source, table_number) DO UPDATE SET
                        title = EXCLUDED.title,
                        full_csv = EXCLUDED.full_csv,
                        rows_json = EXCLUDED.rows_json
                    RETURNING id
                    """,
                    (source, table_number, title, full_csv, Jsonb(records)),
                ).fetchone()["id"]
                connection.execute(
                    "DELETE FROM policy_table_vectors WHERE table_id = %s", (table_id,)
                )

                search_texts = [
                    row_search_text(source, title, headers, row) for row in rows
                ]
                if not search_texts:
                    search_texts = [
                        f"Source: {source}\nTable: {title}\nColumns: {', '.join(headers)}"
                    ]
                embeddings = embedding_model.encode(
                    search_texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                for row_number, (search_text, embedding) in enumerate(
                    zip(search_texts, embeddings, strict=True), 1
                ):
                    connection.execute(
                        """
                        INSERT INTO policy_table_vectors
                            (table_id, row_number, search_text, embedding)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (table_id, row_number, search_text, embedding),
                    )
                table_count += 1
                row_count += len(search_texts)
            connection.commit()

    print(
        f"Ingested {table_count} parent tables and {row_count} searchable child rows."
    )


def retrieve_tables(
    connection: psycopg.Connection,
    embedding_model: SentenceTransformer,
    query: str,
    top_tables: int,
    candidate_rows: int,
) -> list[dict[str, Any]]:
    query_embedding = embedding_model.encode(query, normalize_embeddings=True)
    return connection.execute(
        """
        WITH row_hits AS (
            SELECT
                table_id,
                row_number,
                search_text,
                1 - (embedding <=> %(embedding)s) AS similarity
            FROM policy_table_vectors
            ORDER BY embedding <=> %(embedding)s
            LIMIT %(candidate_rows)s
        ),
        ranked_tables AS (
            SELECT table_id, MAX(similarity) AS similarity
            FROM row_hits
            GROUP BY table_id
        )
        SELECT
            t.id,
            t.source,
            t.table_number,
            t.title,
            t.full_csv,
            t.rows_json,
            r.similarity
        FROM ranked_tables AS r
        JOIN policy_tables AS t ON t.id = r.table_id
        ORDER BY r.similarity DESC
        LIMIT %(top_tables)s
        """,
        {
            "embedding": query_embedding,
            "candidate_rows": candidate_rows,
            "top_tables": top_tables,
        },
    ).fetchall()


def print_retrieval(results: list[dict[str, Any]]) -> None:
    for rank, result in enumerate(results, 1):
        print(
            f"\n=== TABLE {rank}: {result['source']} / {result['title']} "
            f"(similarity={result['similarity']:.4f}) ===\n"
        )
        print(result["full_csv"], end="")


def generate_answer(query: str, results: list[dict[str, Any]], model: str) -> str:
    context = "\n\n".join(
        f"SOURCE: {result['source']}\nTABLE: {result['title']}\n{result['full_csv']}"
        for result in results
    )
    client = OpenAI()
    response = client.responses.create(
        model=model,
        instructions=(
            "Answer only from the supplied policy tables. Cite the source filename and table title. "
            "If the tables do not contain the answer, say that the supplied tables are insufficient."
        ),
        input=f"Question:\n{query}\n\nRetrieved tables:\n{context}",
    )
    return response.output_text


def main() -> None:
    # Project-specific settings should replace stale values exported by a
    # previous shell session.
    load_dotenv(override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("input_dir", type=Path)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-tables", type=int, default=1)
    search_parser.add_argument("--candidate-rows", type=int, default=20)

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("query")
    ask_parser.add_argument("--top-tables", type=int, default=1)
    ask_parser.add_argument("--candidate-rows", type=int, default=20)
    ask_parser.add_argument(
        "--model", default=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    )

    args = parser.parse_args()
    if args.command == "init-db":
        initialize_database(args.database_url)
        return

    embedding_model = load_embedding_model(args.embedding_model)
    if args.command == "ingest":
        ingest(
            args.database_url, args.input_dir.expanduser().resolve(), embedding_model
        )
        return

    with connect(args.database_url) as connection:
        results = retrieve_tables(
            connection,
            embedding_model,
            args.query,
            args.top_tables,
            args.candidate_rows,
        )
    if not results:
        raise RuntimeError("No tables were retrieved. Run init-db and ingest first.")

    if args.command == "search":
        print_retrieval(results)
    else:
        try:
            print(generate_answer(args.query, results, args.model))
        except AuthenticationError:
            raise SystemExit(
                "OpenAI rejected OPENAI_API_KEY. Replace the key in the active environment "
                "or .env, then rerun the ask command."
            ) from None
        except PermissionDeniedError:
            raise SystemExit(
                f"The configured OpenAI project cannot use {args.model!r}. "
                "Set OPENAI_MODEL or pass --model with an accessible model."
            ) from None


if __name__ == "__main__":
    main()
