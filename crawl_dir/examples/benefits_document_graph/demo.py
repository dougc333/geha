"""Query-time versus prebuilt document links using synthetic benefits data."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPH = HERE / "graph.json"


def load_documents() -> dict[str, dict]:
    data = json.loads((HERE / "documents.json").read_text())
    return {doc["id"]: doc for doc in data}


def build_graph(documents: dict[str, dict]) -> dict:
    """Ingestion-time benefit links contain IDs, never full PDF text."""
    by_benefit: dict[str, list[str]] = defaultdict(list)
    for doc in documents.values():
        for benefit in doc["benefits"]:
            by_benefit[benefit].append(doc["id"])
    return {"by_benefit": {key: sorted(ids) for key, ids in by_benefit.items()}}


def candidates(documents: dict[str, dict], graph: dict | None,
               seed: dict, benefit: str) -> tuple[list[str], int]:
    if graph is None:
        # Query-time approach: inspect every other document profile again.
        ids = [doc["id"] for doc in documents.values()
               if doc["id"] != seed["id"] and benefit in doc["benefits"]]
        return ids, len(documents) - 1
    # Prebuilt approach: follow a saved benefit link.
    ids = [doc_id for doc_id in graph["by_benefit"].get(benefit, [])
           if doc_id != seed["id"]]
    return ids, len(ids)


def judge_relation(seed: dict, candidate: dict, benefit: str,
                   industries: set[str]) -> bool:
    """Stand-in for an LLM judging compact document profiles."""
    return (candidate["industry"] in industries
            and benefit in candidate["benefits"]
            and candidate["measure"] == seed["measure"]
            and candidate["year"] == seed["year"])


def answer_context(selected: list[dict], benefit: str) -> list[dict]:
    """Only these cited observations would enter the answer LLM context."""
    return [
        {"document": doc["title"], "industry": doc["industry"],
         "year": doc["year"], "measure": doc["measure"],
         "percent": obs["percent"], "page": obs["page"],
         "evidence": obs["evidence"]}
        for doc in selected for obs in doc["observations"]
        if obs["benefit"] == benefit
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="Build reusable benefit-to-document links")
    query = commands.add_parser("query", help="Compare industries from one seed")
    query.add_argument("--mode", choices=("query-time", "prebuilt"), required=True)
    query.add_argument("--seed", default="overview")
    query.add_argument("--benefit", default="paid_leave")
    query.add_argument("--industries", default="retail,manufacturing")
    args = parser.parse_args()

    documents = load_documents()
    if args.command == "build":
        GRAPH.write_text(json.dumps(build_graph(documents), indent=2) + "\n")
        print(f"Built {GRAPH} from {len(documents)} document profiles")
        return

    seed = documents[args.seed]
    if args.benefit not in seed["benefits"]:
        parser.error("The seed document does not discuss that benefit")
    if args.mode == "prebuilt" and not GRAPH.exists():
        parser.error("Run `python demo.py build` first")
    graph = json.loads(GRAPH.read_text()) if args.mode == "prebuilt" else None
    ids, checked = candidates(documents, graph, seed, args.benefit)
    industries = set(args.industries.split(","))
    selected = sorted(
        (documents[doc_id] for doc_id in ids
         if judge_relation(seed, documents[doc_id], args.benefit, industries)),
        key=lambda doc: doc["industry"],
    )
    context = answer_context(selected, args.benefit)

    print(f"Mode: {args.mode}")
    print(f"Seed: {seed['title']}")
    print(f"Document profiles considered: {checked}")
    print(f"Included documents: {', '.join(doc['id'] for doc in selected)}")
    print("\nOnly this evidence goes to the answer LLM:")
    print(json.dumps(context, indent=2))
    if len(context) == 2:
        low, high = sorted(context, key=lambda item: item["percent"])
        print(f"\nDerived comparison: {high['industry']} exceeds {low['industry']} "
              f"by {high['percent'] - low['percent']} percentage points "
              f"({high['percent']}% vs {low['percent']}%).")


if __name__ == "__main__":
    main()
