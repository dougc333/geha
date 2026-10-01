#!/usr/bin/env python3
"""Score retrieval setups on evals/questions.jsonl.

    python evals/run_eval.py [--no-rerank] [--no-weaviate]

Runs every question through each setup, using the deployed query code
(query/chat.py, query/app.py, query/weaviate_store.py) against the live Neon,
Weaviate and Bedrock, and reports:

  page hit@k  the gold page is among the top k chunks (k = 1, 5, 10)
  MRR@10      mean of 1/rank of the first gold-page chunk (0 if not in the top 10)
  paper hit@5 any chunk from the gold paper is in the top 5

Setups (all searching every paper, like the chatbot):
  pg-keyword       Postgres full-text only
  pg-vector        pgvector only (Titan embeddings)
  pg-hybrid        keyword + vector top 25 each, reciprocal-rank fusion (chatbot default)
  pg-bm25          Okapi BM25 computed in SQL over the tsvector (chat.bm25_search)
  pg-hybrid-2:1    pg-hybrid with the vector list weighted double in RRF
  pg-hybrid-bm25   vector + SQL BM25, reciprocal-rank fusion
  pg-hybrid+rerank pg-hybrid top 50 reranked by Amazon Rerank (what the chatbot uses)
  pg-vector+rerank pgvector top 50 reranked (no keyword search)
  pg-hybrid-bm25+rerank  pg-hybrid-bm25 top 50 reranked
  wv-a0 … wv-a1    Weaviate hybrid, alpha 0 (BM25) to 1 (vector), relative-score fusion
  wv-ranked        Weaviate hybrid alpha 0.5 with rank-based fusion
  wv-a0.5+rerank   Weaviate hybrid top 50 reranked by Amazon Rerank

Writes evals/results.json (every ranking) and evals/results.md (summary tables).
Timings are measured from this machine, not the Lambda, so compare them only
with each other; a retriever shared by several setups is timed only where it runs
first (later setups reuse its cached result). Cost: ~$0.001 per question per rerank setup (~$0.08 total).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "query"))


def search_units(candidate_count: int, unit_size: int = 100) -> int:
    """Bedrock rerank search units for one request (priced per 100 candidates)."""
    if candidate_count < 0:
        raise ValueError("candidate_count must be non-negative")
    return math.ceil(candidate_count / unit_size) if candidate_count else 0


def cost_summary(*, representation: str, question_count: int, embedding_calls: int,
                 rerank_calls: int, rerank_search_units: int, embedding_model: str,
                 rerank_model: str, rerank_price_per_unit: float,
                 started_at: str, finished_at: str) -> dict:
    """Machine-readable cost evidence based on observed evaluator call counts."""
    return {
        "representation": representation,
        "question_count": question_count,
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "embedding": {
            "model": embedding_model,
            "calls": embedding_calls,
            "input_tokens": None,
            "estimated_cost_usd": None,
            "note": "The evaluator reuses one query embedding across setups; token usage is not returned by app._embed_query.",
        },
        "rerank": {
            "model": rerank_model,
            "calls": rerank_calls,
            "search_units": rerank_search_units,
            "price_per_search_unit_usd": rerank_price_per_unit,
            "estimated_cost_usd": round(rerank_search_units * rerank_price_per_unit, 6),
        },
    }


def load_secrets(region: str) -> None:
    # Eval runs shouldn't send traces to the chatbot's Langfuse project (and stale
    # LANGFUSE_* keys in a shell made every batch fail with 401).
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"
    ssm = boto3.client("ssm", region_name=region)
    for env, name in {"DATABASE_URL": "/rag-demo/database-url",
                      "WEAVIATE_URL": "/rag-demo/weaviate-url",
                      "WEAVIATE_API_KEY": "/rag-demo/weaviate-api-key"}.items():
        if env not in os.environ:
            os.environ[env] = ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]
    os.environ.setdefault("AWS_REGION", region)


def metrics(ranked: list[dict], gold: dict) -> dict:
    ranks = [i for i, r in enumerate(ranked[:10], start=1)
             if r["document_id"] == gold["document_id"] and r["page"] == gold["page"]]
    first = ranks[0] if ranks else None
    return {
        "rank": first,
        "hit1": first == 1, "hit5": bool(first and first <= 5), "hit10": first is not None,
        # Each benchmark question has one gold page, so page Recall@5 is binary:
        # the relevant page was retrieved in the first five results or it was not.
        "recall5": float(bool(first and first <= 5)),
        "rr": 1 / first if first else 0.0,
        # With one binary relevance judgment, ideal DCG is 1.0 and nDCG is the
        # log-discounted gain of the first result from the gold page.
        "ndcg10": 1 / math.log2(first + 1) if first else 0.0,
        "paper_hit5": any(r["document_id"] == gold["document_id"] for r in ranked[:5]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--no-rerank", action="store_true", help="skip the two rerank setups (no cost)")
    parser.add_argument("--no-weaviate", action="store_true")
    parser.add_argument("--types", default="", help="only these question types, e.g. table or fact,paraphrase")
    parser.add_argument("--out", default="results", help="output file stem in evals/")
    parser.add_argument("--representation", default="current", help="label for the indexed document representation")
    parser.add_argument("--core-matrix", action="store_true",
                        help="run only BM25, vector and BM25+vector RRF, each with and without reranking")
    parser.add_argument("--setups", default="",
                        help="comma-separated setup names to run, e.g. pg-hybrid-bm25")
    args = parser.parse_args()
    started_at = dt.datetime.now(dt.UTC).isoformat()
    load_secrets(args.region)

    import app  # noqa: E402  (needs the environment above)
    import chat  # noqa: E402
    import weaviate_store  # noqa: E402
    from rag_core import reciprocal_rank_fusion  # noqa: E402

    questions = [json.loads(l) for l in (HERE / "questions.jsonl").read_text().splitlines() if l.strip()]
    if args.types:
        questions = [q for q in questions if q["type"] in args.types.split(",")]

    # Retriever results are computed once per question and shared by every setup
    # that uses them (SQL BM25 takes seconds, so recomputing it per setup was slow).
    cache: dict[tuple, list[dict]] = {}

    def cached(key: tuple, compute):
        if key not in cache:
            cache[key] = compute()
        return cache[key]

    def pg_hybrid(conn, q, emb, limit=25):
        return reciprocal_rank_fusion([
            cached(("vector", q, limit), lambda: chat.vector_search(conn, emb, limit=limit)),
            cached(("fts", q, limit), lambda: chat.keyword_search(conn, q, limit=limit))])

    def pg_hybrid_bm25(conn, q, emb, limit=25):
        return reciprocal_rank_fusion([
            cached(("vector", q, limit), lambda: chat.vector_search(conn, emb, limit=limit)),
            cached(("bm25", q, limit), lambda: chat.bm25_search(conn, q, limit=limit))])

    def pg_hybrid_weighted(conn, q, emb, limit=25):  # vector counts double
        return reciprocal_rank_fusion([
            cached(("vector", q, limit), lambda: chat.vector_search(conn, emb, limit=limit)),
            cached(("fts", q, limit), lambda: chat.keyword_search(conn, q, limit=limit))], weights=[2, 1])

    usage = {"embedding_calls": 0, "rerank_calls": 0, "rerank_search_units": 0}

    def rerank(q, rows):
        candidates = [dict(r) for r in rows[:50]]
        usage["rerank_calls"] += 1
        usage["rerank_search_units"] += search_units(len(candidates))
        return app._rerank(q, candidates)

    setups = {
        "pg-keyword": lambda conn, q, emb: cached(("fts", q, 25), lambda: chat.keyword_search(conn, q, limit=25))[:10],
        "pg-bm25": lambda conn, q, emb: cached(("bm25", q, 25), lambda: chat.bm25_search(conn, q, limit=25))[:10],
        "pg-vector": lambda conn, q, emb: cached(("vector", q, 25), lambda: chat.vector_search(conn, emb, limit=25))[:10],
        "pg-hybrid": pg_hybrid,
        "pg-hybrid-2:1": pg_hybrid_weighted,
        "pg-hybrid-bm25": pg_hybrid_bm25,
    }
    if not args.no_rerank:
        setups["pg-hybrid+rerank"] = lambda conn, q, emb: rerank(q, pg_hybrid(conn, q, emb))
        setups["pg-bm25+rerank"] = lambda conn, q, emb: rerank(
            q, cached(("bm25", q, 50), lambda: chat.bm25_search(conn, q, limit=50)))
        setups["pg-vector+rerank"] = lambda conn, q, emb: rerank(q, chat.vector_search(conn, emb, limit=50))
        setups["pg-hybrid-bm25+rerank"] = lambda conn, q, emb: rerank(q, pg_hybrid_bm25(conn, q, emb))
    if not args.no_weaviate:
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            setups[f"wv-a{alpha:g}"] = (lambda a: lambda conn, q, emb: weaviate_store.hybrid(q, emb, alpha=a, limit=10))(alpha)
        setups["wv-ranked"] = lambda conn, q, emb: weaviate_store.hybrid(q, emb, alpha=0.5, fusion="ranked", limit=10)
        if not args.no_rerank:
            setups["wv-a0.5+rerank"] = lambda conn, q, emb: rerank(q, weaviate_store.hybrid(q, emb, alpha=0.5, limit=50))

    if args.core_matrix:
        core = (
            "pg-bm25", "pg-vector", "pg-hybrid-bm25",
            "pg-bm25+rerank", "pg-vector+rerank", "pg-hybrid-bm25+rerank",
        )
        setups = {name: setups[name] for name in core if name in setups}

    if args.setups:
        requested = [name.strip() for name in args.setups.split(",") if name.strip()]
        unknown = [name for name in requested if name not in setups]
        if unknown:
            parser.error(
                f"unknown setup(s): {', '.join(unknown)}; "
                f"available: {', '.join(sorted(setups))}"
            )
        setups = {name: setups[name] for name in requested}

    results = {name: [] for name in setups}
    with app.database() as conn:
        for n, gold in enumerate(questions, start=1):
            emb = app._embed_query(gold["question"])
            usage["embedding_calls"] += 1
            cache.clear()
            for name, run in setups.items():
                started = time.perf_counter()
                ranked = run(conn, gold["question"], emb)
                ms = (time.perf_counter() - started) * 1000
                results[name].append({"id": gold["id"], "type": gold["type"], "ms": round(ms, 1),
                                      **metrics(ranked, gold),
                                      "top5": [(r["title"][:40], r["page"]) for r in ranked[:5]]})
            print(f"{n}/{len(questions)} {gold['id']}: " + " ".join(
                f"{name}={results[name][-1]['rank'] or '-'}" for name in setups), flush=True)

    def summary(rows: list[dict]) -> dict:
        return {
            "hit@1": statistics.mean(r["hit1"] for r in rows),
            "hit@5": statistics.mean(r["hit5"] for r in rows),
            "hit@10": statistics.mean(r["hit10"] for r in rows),
            "Recall@5": statistics.mean(r["recall5"] for r in rows),
            "MRR@10": statistics.mean(r["rr"] for r in rows),
            "nDCG@10": statistics.mean(r["ndcg10"] for r in rows),
            "paper hit@5": statistics.mean(r["paper_hit5"] for r in rows),
        }

    table = {name: {**summary(rows),
                    **{f"{t} hit@5": summary([r for r in rows if r["type"] == t])["hit@5"]
                       for t in sorted({q["type"] for q in questions})},
                    "median ms": statistics.median(r["ms"] for r in rows)}
             for name, rows in results.items()}
    finished_at = dt.datetime.now(dt.UTC).isoformat()
    costs = cost_summary(
        representation=args.representation,
        question_count=len(questions),
        embedding_calls=usage["embedding_calls"],
        rerank_calls=usage["rerank_calls"],
        rerank_search_units=usage["rerank_search_units"],
        embedding_model=app.EMBEDDING_MODEL,
        rerank_model=app.RERANK_MODEL,
        rerank_price_per_unit=app.RERANK_PRICE_PER_UNIT,
        started_at=started_at,
        finished_at=finished_at,
    )
    (HERE / f"{args.out}.json").write_text(json.dumps({
        "representation": args.representation,
        "summary": table,
        "cost_evidence": costs,
        "per_question": results,
    }, indent=2))
    (HERE / f"{args.out}_cost.json").write_text(json.dumps(costs, indent=2) + "\n")

    cols = (["hit@1", "hit@5", "hit@10", "Recall@5", "MRR@10", "nDCG@10", "paper hit@5"]
            + [f"{t} hit@5" for t in sorted({q["type"] for q in questions})] + ["median ms"])
    counts = ", ".join(f"{sum(q['type'] == t for q in questions)} {t}"
                       for t in sorted({q["type"] for q in questions}))
    lines = [f"# Retrieval eval: {len(questions)} questions ({counts})",
             f"\nRepresentation: `{args.representation}`\n",
             "| setup | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, row in table.items():
        lines.append(f"| {name} | " + " | ".join(
            f"{row[c]:.0f}" if c == "median ms" else f"{row[c]:.2f}" for c in cols) + " |")
    lines.extend([
        "\n## Cost evidence",
        "",
        "| item | value |",
        "|---|---:|",
        f"| Query embedding calls | {costs['embedding']['calls']} |",
        f"| Reranker calls | {costs['rerank']['calls']} |",
        f"| Reranker search units | {costs['rerank']['search_units']} |",
        f"| Reranker unit price | ${costs['rerank']['price_per_search_unit_usd']:.4f} |",
        f"| Estimated reranker cost | ${costs['rerank']['estimated_cost_usd']:.3f} |",
        "",
        "Embedding token usage is not exposed by the current evaluator, so the cost file records calls but does not invent an embedding charge.",
    ])
    (HERE / f"{args.out}.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
