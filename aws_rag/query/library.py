"""Questions about the library itself, answered from rag_documents with SQL.

Used by the chatbot's router (chat.py) for "list/count/which papers" questions
and by GET /api/documents for its filters. No model or chunk search involved,
so answers are exact and complete.
"""

from __future__ import annotations

import re

from rag_core import tokenize

COLUMNS = """d.id, d.title, d.source, d.arxiv_id, d.authors, d.published,
             d.primary_category, (SELECT count(*) FROM rag_chunks c WHERE c.document_id = d.id)"""
# Searchable text for "papers about X": title plus arXiv abstract.
DOC_TEXT = "to_tsvector('english', d.title || ' ' || coalesce(d.abstract, ''))"


def _row(r: tuple) -> dict:
    return {
        "id": r[0], "title": r[1], "source": r[2], "arxiv_id": r[3], "authors": r[4] or [],
        "published": r[5].isoformat() if r[5] else None, "primary_category": r[6], "chunks": r[7],
    }


def find_papers(connection, *, author: str | None = None, year_from: int | None = None,
                year_to: int | None = None, category: str | None = None,
                title_contains: str | None = None, topic: str | None = None,
                limit: int | None = None) -> list[dict]:
    """Papers matching every given filter; by relevance when `topic` is set, else by title."""
    where, params = [], []
    if author:
        # Whole words, case-insensitive: "He" matches "Kaiming He", not "Shen".
        where.append("EXISTS (SELECT 1 FROM unnest(d.authors) a WHERE a ~* %s)")
        params.append(r"\m" + re.escape(author.strip()) + r"\M")
    if year_from:
        where.append("d.published >= make_date(%s, 1, 1)")
        params.append(year_from)
    if year_to:
        where.append("d.published < make_date(%s, 1, 1)")
        params.append(year_to + 1)
    if category:
        where.append("(d.primary_category = %s OR %s = ANY(d.categories))")
        params += [category, category]
    if title_contains:
        where.append("d.title ILIKE %s")
        params.append(f"%{title_contains}%")

    def run(query_text: str | None) -> list[dict]:
        clauses, values = list(where), list(params)
        order = "d.title"
        if query_text:
            clauses.append(f"{DOC_TEXT} @@ websearch_to_tsquery('english', %s)")
            values.append(query_text)
            order = f"ts_rank_cd({DOC_TEXT}, websearch_to_tsquery('english', %s), 32) DESC, d.title"
            values_order = [query_text]
        else:
            values_order = []
        sql = (f"SELECT {COLUMNS} FROM rag_documents d"
               + (f" WHERE {' AND '.join(clauses)}" if clauses else "")
               + f" ORDER BY {order}" + (" LIMIT %s" if limit else ""))
        return [_row(r) for r in connection.execute(
            sql, values + values_order + ([limit] if limit else [])).fetchall()]

    if not topic:
        return run(None)
    # All topic words first ("object detection" → object AND detection); if
    # nothing matches, fall back to any word.
    return run(topic) or run(" or ".join(tokenize(topic)))
