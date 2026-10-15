"""Compare row-vector and full-table-vector retrieval on the same policy tables."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from evaluate_table_preferences import extract_products, score_products
from table_rag import (
    DEFAULT_DATABASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    connect,
    load_embedding_model,
    retrieve_tables,
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS policy_table_full_vectors (
    table_id bigint PRIMARY KEY REFERENCES policy_tables(id) ON DELETE CASCADE,
    search_text text NOT NULL,
    embedding vector(384) NOT NULL
);
CREATE INDEX IF NOT EXISTS policy_table_full_vectors_embedding_hnsw
ON policy_table_full_vectors USING hnsw (embedding vector_cosine_ops);
"""


def full_table_search_text(table: dict[str, Any]) -> str:
    """Use the same source and title metadata as the row search strings."""
    return (
        f"Source: {table['source']}\n"
        f"Table: {table['title']}\n"
        f"{table['full_csv']}"
    )


def index_full_tables(connection, embedding_model) -> dict[str, int]:
    """Build a separate one-vector-per-table index without changing row vectors."""
    connection.execute(SCHEMA_SQL)
    tables = connection.execute(
        "SELECT id, source, title, full_csv FROM policy_tables ORDER BY id"
    ).fetchall()
    if not tables:
        raise RuntimeError("policy_tables is empty; run table_rag.py ingest first")

    texts = [full_table_search_text(table) for table in tables]
    embeddings = embedding_model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    )
    for table, text, embedding in zip(tables, texts, embeddings, strict=True):
        connection.execute(
            """
            INSERT INTO policy_table_full_vectors (table_id, search_text, embedding)
            VALUES (%s, %s, %s)
            ON CONFLICT (table_id) DO UPDATE SET
                search_text = EXCLUDED.search_text,
                embedding = EXCLUDED.embedding
            """,
            (table["id"], text, embedding),
        )
    connection.execute(
        "DELETE FROM policy_table_full_vectors WHERE table_id <> ALL(%s)",
        ([table["id"] for table in tables],),
    )
    connection.commit()
    return {"tables_indexed": len(tables)}


def retrieve_full_tables(connection, query_embedding, top_tables: int):
    return connection.execute(
        """
        SELECT t.id, t.source, t.table_number, t.title, t.full_csv, t.rows_json,
               1 - (v.embedding <=> %(embedding)s) AS similarity
        FROM policy_table_full_vectors AS v
        JOIN policy_tables AS t ON t.id = v.table_id
        ORDER BY v.embedding <=> %(embedding)s
        LIMIT %(top_tables)s
        """,
        {"embedding": query_embedding, "top_tables": top_tables},
    ).fetchall()


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def relation_rows(full_csv: str, case: dict[str, Any]) -> list[dict[str, str]]:
    """Select and project complete CSV rows for an exact cell-relation check."""
    reader = csv.DictReader(io.StringIO(full_csv))
    rows = []
    for raw in reader:
        row = {normalized(key): value for key, value in raw.items() if key}
        if all(normalized(row.get(key, "")) == normalized(value)
               for key, value in case["where"].items()):
            rows.append({key: normalized(row.get(key, "")) for key in case["fields"]})
    return rows


def score_case(case: dict[str, Any], retrieved: list[dict[str, Any]]) -> dict[str, Any]:
    rank = next(
        (
            i for i, table in enumerate(retrieved, 1)
            if table["source"] == case["source"]
            and table["table_number"] == case["table_number"]
        ),
        None,
    )
    top = retrieved[0] if retrieved else None
    if case["kind"] == "preference":
        actual = extract_products(top["full_csv"], case["preference"]) if top else []
        product_score = score_products(actual, case["gold_phrases"])
        exact = product_score["exact_match"]
        detail = {"actual_products": actual, "product_score": product_score}
    else:
        actual_rows = relation_rows(top["full_csv"], case) if top else []
        expected_rows = [
            {key: normalized(row[key]) for key in case["fields"]}
            for row in case["gold_rows"]
        ]
        actual_set = {tuple(row[key] for key in case["fields"]) for row in actual_rows}
        expected_set = {tuple(row[key] for key in case["fields"]) for row in expected_rows}
        exact = actual_set == expected_set
        detail = {"actual_rows": actual_rows, "expected_rows": expected_rows}
    return {
        "gold_table_rank": rank,
        "table_hit_at_1": rank == 1,
        "table_hit_at_3": rank is not None and rank <= 3,
        "table_hit_at_5": rank is not None and rank <= 5,
        "answer_exact_match": exact,
        "top_source": top["source"] if top else None,
        "top_table_number": top["table_number"] if top else None,
        **detail,
    }


def summary(results: list[dict[str, Any]], mode: str, kind: str) -> dict[str, Any]:
    rows = [result[mode] for result in results if result["kind"] == kind]
    if not rows:
        return {"cases": 0}
    return {
        "cases": len(rows),
        "table_hit_at_1": sum(row["table_hit_at_1"] for row in rows) / len(rows),
        "table_hit_at_3": sum(row["table_hit_at_3"] for row in rows) / len(rows),
        "table_hit_at_5": sum(row["table_hit_at_5"] for row in rows) / len(rows),
        "answer_exact_match": sum(row["answer_exact_match"] for row in rows) / len(rows),
    }


def compare(connection, embedding_model, preference_cases, relation_cases,
            top_tables: int, candidate_rows: int) -> dict[str, Any]:
    table_count = connection.execute("SELECT count(*) AS n FROM policy_tables").fetchone()["n"]
    if connection.execute("SELECT to_regclass('policy_table_full_vectors') AS name").fetchone()["name"] is None:
        raise RuntimeError("full-table index is missing; run the index command")
    full_count = connection.execute(
        "SELECT count(*) AS n FROM policy_table_full_vectors"
    ).fetchone()["n"]
    if not table_count or full_count != table_count:
        raise RuntimeError("full-table index is missing or stale; run the index command")

    cases = [{**case, "kind": "preference"} for case in preference_cases] + [
        {**case, "kind": "relation"} for case in relation_cases
    ]
    results = []
    for case in cases:
        query = case["query"]
        row_results = retrieve_tables(
            connection, embedding_model, query,
            top_tables=top_tables, candidate_rows=candidate_rows,
        )
        query_embedding = embedding_model.encode(query, normalize_embeddings=True)
        full_results = retrieve_full_tables(connection, query_embedding, top_tables)
        results.append({
            "id": case["id"], "kind": case["kind"], "query": query,
            "source": case["source"], "table_number": case["table_number"],
            "row_vectors": score_case(case, row_results),
            "full_table_vectors": score_case(case, full_results),
        })
    summaries = {
        mode: {kind: summary(results, mode, kind)
               for kind in ("preference", "relation")}
        for mode in ("row_vectors", "full_table_vectors")
    }
    return {
        "configuration": {
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "top_tables": top_tables,
            "candidate_rows": candidate_rows,
            "table_corpus_size": table_count,
            "answer_mode": "deterministic extraction from top retrieved parent table",
            "full_table_embedding_note": "The embedding model may truncate long full-table search strings to its token limit.",
        },
        "summary": summaries,
        "results": results,
    }


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"), override=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("index", "compare", "all"))
    parser.add_argument("--database-url", default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--preference-evals", type=Path, default=Path(__file__).with_name("table_preference_evals.json"))
    parser.add_argument("--relation-evals", type=Path, default=Path(__file__).with_name("table_relation_evals.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("table_ablation_results.json"))
    parser.add_argument("--top-tables", type=int, default=5)
    parser.add_argument("--candidate-rows", type=int, default=20)
    args = parser.parse_args()
    embedding_model = load_embedding_model(args.embedding_model)
    with connect(args.database_url) as connection:
        if args.command in ("index", "all"):
            print(json.dumps(index_full_tables(connection, embedding_model)))
        if args.command in ("compare", "all"):
            report = compare(
                connection, embedding_model,
                json.loads(args.preference_evals.read_text()),
                json.loads(args.relation_evals.read_text()),
                args.top_tables, args.candidate_rows,
            )
            report["configuration"]["embedding_model"] = args.embedding_model
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report["summary"], indent=2))
            print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
