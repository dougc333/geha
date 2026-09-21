"""Parent-child RAG over tables extracted from GEHA coverage policies."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from openai import AuthenticationError, OpenAI, PermissionDeniedError
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from sentence_transformers import SentenceTransformer

try:  # Support module and direct-script execution.
    from .billing_code_data import docling_billing_rows
    from .html_table_data import load_policy_html_tables
except ImportError:  # pragma: no cover - direct CLI execution
    from billing_code_data import docling_billing_rows
    from html_table_data import load_policy_html_tables

DEFAULT_DATABASE_URL = "postgresql://geha:geha-local@127.0.0.1:5433/geha_rag"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DOCLING_SUFFIX = ".docling.md"


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_tables (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    table_number integer NOT NULL,
    title text NOT NULL,
    full_html text NOT NULL,
    rows_json jsonb NOT NULL,
    conditions_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    indication_context text NOT NULL DEFAULT '',
    UNIQUE (source, table_number)
);

ALTER TABLE policy_tables
    ADD COLUMN IF NOT EXISTS conditions_json jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE policy_tables
    ADD COLUMN IF NOT EXISTS indication_context text NOT NULL DEFAULT '';
ALTER TABLE policy_tables
    ADD COLUMN IF NOT EXISTS full_html text NOT NULL DEFAULT '';
ALTER TABLE policy_tables
    ALTER COLUMN full_html DROP DEFAULT;
ALTER TABLE policy_tables
    DROP COLUMN IF EXISTS full_csv;

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

CREATE TABLE IF NOT EXISTS policy_chunks (
    source_pdf text NOT NULL,
    chunk_number integer NOT NULL,
    section_type text NOT NULL,
    condition text,
    content text NOT NULL,
    PRIMARY KEY (source_pdf, chunk_number)
);

CREATE INDEX IF NOT EXISTS policy_chunks_source_section_condition
ON policy_chunks (source_pdf, section_type, condition);

CREATE TABLE IF NOT EXISTS policy_source_terms (
    source_pdf text NOT NULL,
    term text NOT NULL,
    term_type text NOT NULL,
    PRIMARY KEY (source_pdf, term)
);

CREATE INDEX IF NOT EXISTS policy_source_terms_term
ON policy_source_terms (term);

CREATE TABLE IF NOT EXISTS policy_billing_codes (
    source_pdf text NOT NULL,
    table_name text NOT NULL,
    code text NOT NULL,
    item_name text NOT NULL,
    raw_code_cell text NOT NULL,
    source_line integer NOT NULL,
    PRIMARY KEY (source_pdf, table_name, source_line, code)
);

CREATE INDEX IF NOT EXISTS policy_billing_codes_code
ON policy_billing_codes (code);
"""


def normalized_table(rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    if len(rows) > 1 and rows[0] == [str(index) for index in range(len(rows[0]))]:
        rows = rows[1:]
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


def is_revision_history_table(headers: list[str]) -> bool:
    return infer_title(headers).casefold() == "revision history"


def table_as_records(headers: list[str], rows: list[list[str]]) -> list[dict[str, str]]:
    return [dict(zip(headers, row, strict=True)) for row in rows]


INDICATION_HEADING_RE = re.compile(
    r"^#{1,6}\s+Indication\s+Specific(?:\s+Approval)?\s+Criteria\s*:?(.*)$",
    re.IGNORECASE,
)
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
UNIVERSAL_HEADING_RE = re.compile(
    r"^#{1,6}\s+Universal\s+Approval\s+Criteria\s*:?\s*$", re.IGNORECASE
)
NON_CONDITION_HEADINGS = {
    "g.e.h.a",
    "geha",
    "limitations",
    "for internal use only",
}


def extract_indication_metadata(markdown_path: Path) -> tuple[list[str], str]:
    """Extract explicit indication headings and their source section from Docling Markdown."""
    if not markdown_path.exists():
        return [], ""

    section_lines: list[str] = []
    candidates: list[str] = []
    in_section = False
    for line in markdown_path.read_text(encoding="utf-8").splitlines():
        indication_match = INDICATION_HEADING_RE.match(line.strip())
        if indication_match:
            in_section = True
            section_lines.append(line)
            inline_condition = indication_match.group(1).strip(" :-")
            if inline_condition:
                candidates.append(inline_condition)
            continue
        if not in_section:
            continue
        if UNIVERSAL_HEADING_RE.match(line.strip()):
            break

        section_lines.append(line)
        heading_match = MARKDOWN_HEADING_RE.match(line.strip())
        if not heading_match:
            continue
        heading = heading_match.group(1).strip().rstrip(":")
        if heading.casefold() in NON_CONDITION_HEADINGS:
            continue
        if candidates and candidates[-1].endswith("-") and heading[:1].islower():
            candidates[-1] = f"{candidates[-1]} {heading}"
        else:
            candidates.append(heading)

    conditions = list(
        dict.fromkeys(
            candidate.strip() for candidate in candidates if candidate.strip()
        )
    )
    context = "\n".join(section_lines).strip()
    return conditions, context


CHUNK_HEADING_RE = re.compile(r"^## Chunk (\d+)\s*$", re.MULTILINE)


def split_markdown_chunks(path: Path) -> list[tuple[int, str]]:
    """Read Docling's numbered chunks without changing their source wording."""
    text = path.read_text(encoding="utf-8")
    headings = list(CHUNK_HEADING_RE.finditer(text))
    chunks: list[tuple[int, str]] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        content = text[heading.end() : end].strip()
        if content:
            chunks.append((int(heading.group(1)), content))
    return chunks


def _heading_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def classify_policy_chunks(
    chunks: list[tuple[int, str]], conditions: list[str]
) -> list[dict[str, Any]]:
    """Label chunks using conditions extracted from the matching Docling document."""
    condition_names = {_heading_key(value): value for value in conditions}
    output: list[dict[str, Any]] = []
    current_type = "overview"
    current_condition: str | None = None
    used_conditions: set[str] = set()
    for number, content in chunks:
        first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
        key = _heading_key(first_line.rstrip(":"))
        condition = condition_names.get(key)
        if not condition and key.startswith("indicationspecificcriteria"):
            suffix = key.removeprefix("indicationspecificcriteria")
            condition = condition_names.get(suffix)
        if not condition and len(key) >= 12:
            condition = next(
                (
                    name for condition_key, name in condition_names.items()
                    if name not in used_conditions and condition_key.endswith(key)
                ),
                None,
            )
        if condition:
            current_type, current_condition = "indication", condition
            used_conditions.add(condition)
        elif key.startswith("universalapprovalcriteria"):
            current_type, current_condition = "universal", None
        elif key.startswith("billing"):
            current_type, current_condition = "billing", None
        elif key.startswith("references"):
            current_type, current_condition = "references", None
        elif key.startswith("disclaimer"):
            current_type, current_condition = "disclaimer", None
        elif key.startswith("revisionhistory"):
            current_type, current_condition = "revision", None
        # A long section may span multiple numbered chunks. In that case the
        # current label carries forward until a new documented heading appears.
        output.append(
            {
                "chunk_number": number,
                "section_type": current_type,
                "condition": current_condition,
                "content": content,
            }
        )
    return output


def policy_source_terms(
    source_pdf: str,
    chunks: list[tuple[int, str]],
    html_tables: list[dict[str, Any]],
    conditions: list[str],
) -> dict[str, str]:
    """Build explicit policy-name and drug-name lookup terms, without an LLM."""
    terms: dict[str, str] = {}

    def add(value: str, kind: str) -> None:
        term = " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
        if len(term) >= 4:
            terms.setdefault(term, kind)

    stem = Path(source_pdf).stem.removeprefix("geha-coverage-policy-")
    add(stem.replace("-", " "), "filename")
    for item in classify_policy_chunks(chunks, conditions)[:3]:
        if item["section_type"] != "overview":
            continue
        content = item["content"]
        first_line = next(
            (line.strip() for line in content.splitlines() if line.strip()), ""
        )
        title_match = re.match(r"^(.+?)\s*[-–]?\s*\(([^)]+)\)", first_line)
        if title_match and "G.E.H.A" not in title_match.group(1):
            add(title_match.group(1), "policy_title")
            add(title_match.group(2), "generic_name")
            break

    for table in html_tables:
        if table["source"] != source_pdf:
            continue
        headers = table["headers"]
        names = [_heading_key(header) for header in headers]
        if "drugname" not in names:
            continue
        name_index = names.index("drugname")
        for row in table["rows"]:
            add(row[name_index], "billing_drug_name")
    return terms


def policy_chunk_paths(input_dir: Path) -> list[Path]:
    """Discover only policy chunks directly inside the selected input directory."""
    return sorted(input_dir.glob("*.docling_chunks.md"))


def ingest_policy_sections(
    database_url: str,
    input_dir: Path,
    html_tables: list[dict[str, Any]] | None = None,
) -> None:
    """Ingest top-level Docling chunks, keeping non-criteria sections out of search results."""
    chunk_paths = policy_chunk_paths(input_dir)
    if not chunk_paths:
        raise FileNotFoundError(f"No *.docling_chunks.md files found in {input_dir}")
    if html_tables is None:
        html_tables = load_policy_html_tables(input_dir)
    section_count = 0
    with connect(database_url) as connection:
        for path in chunk_paths:
            source_pdf = str(path.relative_to(input_dir)).removesuffix(
                ".docling_chunks.md"
            ) + ".pdf"
            markdown_path = path.with_name(
                path.name.removesuffix(".docling_chunks.md") + ".docling.md"
            )
            conditions, _ = extract_indication_metadata(markdown_path)
            chunks = split_markdown_chunks(path)
            labeled = classify_policy_chunks(chunks, conditions)
            terms = policy_source_terms(source_pdf, chunks, html_tables, conditions)
            connection.execute("DELETE FROM policy_chunks WHERE source_pdf = %s", (source_pdf,))
            connection.execute(
                "DELETE FROM policy_source_terms WHERE source_pdf = %s", (source_pdf,)
            )
            for item in labeled:
                connection.execute(
                    """
                    INSERT INTO policy_chunks
                        (source_pdf, chunk_number, section_type, condition, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        source_pdf,
                        item["chunk_number"],
                        item["section_type"],
                        item["condition"],
                        item["content"],
                    ),
                )
            for term, kind in terms.items():
                connection.execute(
                    """
                    INSERT INTO policy_source_terms (source_pdf, term, term_type)
                    VALUES (%s, %s, %s)
                    """,
                    (source_pdf, term, kind),
                )
            section_count += len(labeled)
        connection.commit()
    print(f"Ingested {section_count} chunks from {len(chunk_paths)} Docling files.")


def ingest_billing_codes(database_url: str, input_dir: Path) -> None:
    """Index exact codes from top-level Docling billing and applicable-code tables."""
    markdown_paths = sorted(input_dir.glob("*.docling.md"))
    if not markdown_paths:
        raise FileNotFoundError(f"No *.docling.md files found in {input_dir}")
    code_count = 0
    with connect(database_url) as connection:
        source_pdfs = [path.name.removesuffix(".docling.md") + ".pdf" for path in markdown_paths]
        connection.execute(
            "DELETE FROM policy_billing_codes WHERE source_pdf <> ALL(%s)",
            (source_pdfs,),
        )
        for path in markdown_paths:
            source_pdf = path.name.removesuffix(".docling.md") + ".pdf"
            connection.execute(
                "DELETE FROM policy_billing_codes WHERE source_pdf = %s", (source_pdf,)
            )
            for row in docling_billing_rows(path):
                connection.execute(
                    """
                    INSERT INTO policy_billing_codes
                        (source_pdf, table_name, code, item_name, raw_code_cell, source_line)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        source_pdf,
                        row["table_name"],
                        row["code"],
                        row["item_name"],
                        row["raw_code_cell"],
                        row["line"],
                    ),
                )
                code_count += 1
        connection.commit()
    print(f"Ingested {code_count} billing-code rows from {len(markdown_paths)} Docling files.")


def row_search_text(
    source: str,
    title: str,
    headers: list[str],
    row: list[str],
    conditions: list[str] | None = None,
) -> str:
    values = "; ".join(
        f"{header}: {value}"
        for header, value in zip(headers, row, strict=True)
        if value.strip()
    )
    condition_text = ", ".join(conditions or []) or "Not explicitly enumerated"
    return f"Source: {source}\nTable: {title}\nConditions: {condition_text}\n{values}"


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
    html_tables = load_policy_html_tables(input_dir)
    tables_by_source: dict[str, list[dict[str, Any]]] = {}
    for table in html_tables:
        tables_by_source.setdefault(table["source"], []).append(table)

    table_count = 0
    row_count = 0
    with connect(database_url) as connection:
        indexed_sources = sorted(tables_by_source)
        connection.execute(
            "DELETE FROM policy_tables WHERE source <> ALL(%s)", (indexed_sources,)
        )
        for source, tables in sorted(tables_by_source.items()):
            markdown_path = input_dir / f"{Path(source).stem}{DOCLING_SUFFIX}"
            conditions, indication_context = extract_indication_metadata(markdown_path)
            print(
                f"{source}: {len(tables)} table(s), {len(conditions)} condition(s)",
                flush=True,
            )
            table_numbers = [table["table_number"] for table in tables]
            connection.execute(
                "DELETE FROM policy_tables WHERE source = %s AND table_number <> ALL(%s)",
                (source, table_numbers),
            )

            for table in sorted(tables, key=lambda item: item["table_number"]):
                table_number = table["table_number"]
                headers = table["headers"]
                rows = table["rows"]
                if not headers:
                    continue
                if is_revision_history_table(headers):
                    continue
                title = table["title"]
                full_html = table["full_html"]
                records = table["rows_json"]

                table_id = connection.execute(
                    """
                    INSERT INTO policy_tables
                        (source, table_number, title, full_html, rows_json,
                         conditions_json, indication_context)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, table_number) DO UPDATE SET
                        title = EXCLUDED.title,
                        full_html = EXCLUDED.full_html,
                        rows_json = EXCLUDED.rows_json,
                        conditions_json = EXCLUDED.conditions_json,
                        indication_context = EXCLUDED.indication_context
                    RETURNING id
                    """,
                    (
                        source,
                        table_number,
                        title,
                        full_html,
                        Jsonb(records),
                        Jsonb(conditions),
                        indication_context,
                    ),
                ).fetchone()["id"]
                connection.execute(
                    "DELETE FROM policy_table_vectors WHERE table_id = %s", (table_id,)
                )

                search_texts = [
                    row_search_text(source, title, headers, row, conditions)
                    for row in rows
                ]
                if not search_texts:
                    search_texts = [
                        row_search_text(
                            source,
                            title,
                            ["Columns"],
                            [", ".join(headers)],
                            conditions,
                        )
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
    ingest_policy_sections(database_url, input_dir, html_tables)
    ingest_billing_codes(database_url, input_dir)


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
            t.full_html,
            t.rows_json,
            t.conditions_json,
            t.indication_context,
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
        conditions = result.get("conditions_json") or []
        print(
            f"Conditions: {', '.join(conditions) if conditions else 'Not explicitly enumerated'}"
        )
        print(result["full_html"])


OPENAI_ASK_INSTRUCTIONS = (
    "This is an OpenAI model-generated typo-correction pass, not GEHA source data or an "
    "official coverage determination. Answer only from the supplied policy tables and "
    "structured condition metadata. Correct only obvious typographical errors, OCR errors, "
    "and misspellings in human-readable names. Do not add or remove rows, infer missing "
    "facts, reclassify preference or prior-authorization values, or alter drug names, codes, "
    "numbers, or policy criteria unless the supplied text makes an obvious spelling repair "
    "unambiguous. Preserve uncertain text and identify it as uncertain. Cite the source "
    "filename and table title. An empty CONDITIONS array means the policy did not explicitly "
    "enumerate conditions in an Indication Specific Criteria section. If the supplied "
    "context does not contain the answer, say it is insufficient. Clearly identify any "
    "spelling corrections you applied. Do not use outside medical knowledge to expand the "
    "GEHA evidence."
)


def generate_answer(
    query: str,
    results: list[dict[str, Any]],
    model: str,
    *,
    client: Any | None = None,
) -> str:
    context = "\n\n".join(
        f"SOURCE: {result['source']}\n"
        f"TABLE: {result['title']}\n"
        f"CONDITIONS: {json.dumps(result.get('conditions_json') or [])}\n"
        f"{result['full_html']}"
        for result in results
    )
    openai_client = client or OpenAI()
    response = openai_client.responses.create(
        model=model,
        instructions=OPENAI_ASK_INSTRUCTIONS,
        input=f"Question:\n{query}\n\nRetrieved tables:\n{context}",
        store=False,
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

    sections_parser = subparsers.add_parser("ingest-sections")
    sections_parser.add_argument("input_dir", type=Path)

    billing_parser = subparsers.add_parser("ingest-billing-codes")
    billing_parser.add_argument("input_dir", type=Path)

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

    if args.command == "ingest-sections":
        initialize_database(args.database_url)
        ingest_policy_sections(args.database_url, args.input_dir.expanduser().resolve())
        return

    if args.command == "ingest-billing-codes":
        initialize_database(args.database_url)
        ingest_billing_codes(args.database_url, args.input_dir.expanduser().resolve())
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
