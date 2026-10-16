"""Load human-readable example queries from the table retrieval eval sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVAL_DIRECTORY = Path(__file__).resolve().parent


def _read_json(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, list):
        raise TypeError(f"Expected a list of evaluation cases in {path}")
    return data


def load_eval_queries(directory: Path = EVAL_DIRECTORY) -> list[dict[str, Any]]:
    """Return preference and row-to-column eval cases in one UI-friendly shape."""
    queries: list[dict[str, Any]] = []

    for case in _read_json(directory / "table_preference_evals.json"):
        queries.append(
            {
                "id": case["id"],
                "kind": "Preference lookup",
                "query": case["query"],
                "source": case["source"],
                "table_number": case["table_number"],
                "expected": case["gold_phrases"],
                "preference": case["preference"],
                "requires_all_gold_phrases": case.get(
                    "requires_all_gold_phrases", True
                ),
            }
        )

    taken = {query["id"] for query in queries}
    for case in _read_json(directory / "table_relation_evals.json"):
        # Two relation cases reuse preference-case ids with different questions; results are
        # checkpointed by id, so give them a distinct one.
        case_id = case["id"] if case["id"] not in taken else f"{case['id']}_relation"
        queries.append(
            {
                "id": case_id,
                "kind": "Row-to-column relationship",
                "query": case["query"],
                "source": case["source"],
                "table_number": case["table_number"],
                "expected": case["gold_rows"],
                "where": case.get("where", {}),
                "fields": case.get("fields", []),
            }
        )

    qualifier_path = directory / "table_qualifier_evals.json"
    if qualifier_path.exists():
        for case in _read_json(qualifier_path):
            queries.append(
                {
                    "id": case["id"],
                    "kind": "Qualifier",
                    "qualifier_type": case["qualifier_type"],
                    "query": case["query"],
                    "source": case["source"],
                    "table_number": case["table_number"],
                    "facts": case["facts"],
                    "expected": [fact["text"] for fact in case["facts"]],
                }
            )

    return queries
