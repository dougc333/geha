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
  pg-hybrid+rerank pg-hybrid top 50 reranked by Amazon Rerank (what the chatbot uses)
  wv-a0 … wv-a1    Weaviate hybrid, alpha 0 (BM25) to 1 (vector), relative-score fusion
  wv-ranked        Weaviate hybrid alpha 0.5 with rank-based fusion
  wv-a0.5+rerank   Weaviate hybrid top 50 reranked by Amazon Rerank

Writes evals/results.json (every ranking) and evals/results.md (summary tables).
Timings are measured from this machine, not the Lambda, so compare them only
with each other. Cost: ~$0.001 per question per rerank setup (~$0.08 total).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "query"))


def load_secrets(region: str) -> None:
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
        "rr": 1 / first if first else 0.0,
        "paper_hit5": any(r["document_id"] == gold["document_id"] for r in ranked[:5]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--no-rerank", action="store_true", help="skip the two rerank setups (no cost)")
    parser.add_argument("--no-weaviate", action="store_true")
    args = parser.parse_args()
    load_secrets(args.region)

    import app  # noqa: E402  (needs the environment above)
    import chat  # noqa: E402
    import weaviate_store  # noqa: E402
    from rag_core import reciprocal_rank_fusion  # noqa: E402

    questions = [json.loads(l) for l in (HERE / "questions.jsonl").read_text().splitlines() if l.strip()]

    def pg_hybrid(conn, q, emb, limit=25):
        return reciprocal_rank_fusion([chat.vector_search(conn, emb, limit=limit),
                                       chat.keyword_search(conn, q, limit=limit)])

    setups = {
        "pg-keyword": lambda conn, q, emb: chat.keyword_search(conn, q, limit=10),
        "pg-vector": lambda conn, q, emb: chat.vector_search(conn, emb, limit=10),
        "pg-hybrid": pg_hybrid,
    }
    if not args.no_rerank:
        setups["pg-hybrid+rerank"] = lambda conn, q, emb: app._rerank(q, [dict(r) for r in pg_hybrid(conn, q, emb)[:50]])
    if not args.no_weaviate:
        for alpha in (0.0, 0.25, 0.5, 0.75, 1.0):
            setups[f"wv-a{alpha:g}"] = (lambda a: lambda conn, q, emb: weaviate_store.hybrid(q, emb, alpha=a, limit=10))(alpha)
        setups["wv-ranked"] = lambda conn, q, emb: weaviate_store.hybrid(q, emb, alpha=0.5, fusion="ranked", limit=10)
        if not args.no_rerank:
            setups["wv-a0.5+rerank"] = lambda conn, q, emb: app._rerank(q, weaviate_store.hybrid(q, emb, alpha=0.5, limit=50))

    results = {name: [] for name in setups}
    with app.database() as conn:
        for n, gold in enumerate(questions, start=1):
            emb = app._embed_query(gold["question"])
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
            "MRR@10": statistics.mean(r["rr"] for r in rows),
            "paper hit@5": statistics.mean(r["paper_hit5"] for r in rows),
        }

    table = {name: {**summary(rows),
                    "fact hit@5": summary([r for r in rows if r["type"] == "fact"])["hit@5"],
                    "paraphrase hit@5": summary([r for r in rows if r["type"] == "paraphrase"])["hit@5"],
                    "median ms": statistics.median(r["ms"] for r in rows)}
             for name, rows in results.items()}
    (HERE / "results.json").write_text(json.dumps({"summary": table, "per_question": results}, indent=2))

    cols = ["hit@1", "hit@5", "hit@10", "MRR@10", "paper hit@5", "fact hit@5", "paraphrase hit@5", "median ms"]
    lines = [f"# Retrieval eval: {len(questions)} questions "
             f"({sum(q['type'] == 'fact' for q in questions)} fact, "
             f"{sum(q['type'] == 'paraphrase' for q in questions)} paraphrase)\n",
             "| setup | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for name, row in table.items():
        lines.append(f"| {name} | " + " | ".join(
            f"{row[c]:.0f}" if c == "median ms" else f"{row[c]:.2f}" for c in cols) + " |")
    (HERE / "results.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
