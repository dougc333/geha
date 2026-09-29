#!/usr/bin/env python3
"""Answer accuracy: does the chatbot's answer contain the gold answer?

    python evals/answer_check.py [--types table] [--out answers_tables_flat]

Runs each question through the chatbot's content path (BM25 + vector → RRF →
rerank → Nova Lite answer, via query/chat.py and query/app.py) and counts it
correct when the gold answer appears in the model's answer (case, whitespace,
commas, "%" and trailing zeros ignored). Retrieval metrics say whether the right page was
found; this says whether the model could read the value off it, which matters
for tables flattened into text. Writes evals/<out>.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_eval import load_secrets  # noqa: E402


def norm(text: str) -> str:
    text = text.lower().replace("%", "").replace(",", "")
    text = re.sub(r"(\d+\.\d*?)0+\b", r"\1", text)  # 20.20 -> 20.2
    text = re.sub(r"(\d+)\.\b", r"\1", text)         # 20. -> 20
    return re.sub(r"\s+", "", text)  # "{0.1, 0.3}" == "{ 0.1, 0.3 }"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--types", default="table")
    parser.add_argument("--out", default="answers")
    parser.add_argument("--region", default="us-west-2")
    args = parser.parse_args()
    load_secrets(args.region)
    import app  # noqa: E402
    import chat  # noqa: E402

    questions = [json.loads(l) for l in (HERE / "questions.jsonl").read_text().splitlines() if l.strip()]
    questions = [q for q in questions if q["type"] in args.types.split(",")]
    rows = []
    with app.database() as conn:
        for q in questions:
            started = time.perf_counter()
            candidates = chat._retrieve(conn, q["question"], None, {})
            sources = app._rerank(q["question"], [dict(c) for c in candidates[:50]])[:6]
            context = "\n\n".join(f"[{n}] {s['title']}, page {s['page']}\n{s['content']}"
                                  for n, s in enumerate(sources, 1))
            answer = chat._text(app.converse(
                "answer", modelId=chat.GENERATION_MODEL, system=[{"text": chat.ANSWER_PROMPT}],
                messages=[{"role": "user", "content": [{"text": f"SOURCES:\n{context}\n\nQUESTION:\n{q['question']}"}]}],
                inferenceConfig={"maxTokens": 400, "temperature": 0},
            ))
            correct = norm(q["answer"]) in norm(answer)
            page_found = any(s["document_id"] == q["document_id"] and s["page"] == q["page"] for s in sources)
            rows.append({"id": q["id"], "correct": correct, "gold_page_in_sources": page_found,
                         "gold": q["answer"], "answer": answer, "ms": round((time.perf_counter() - started) * 1000)})
            print(f"{q['id']} {'OK  ' if correct else 'MISS'} page_in_sources={page_found!s:<5} gold={q['answer']!r}  "
                  f"answer={answer[:90]!r}", flush=True)
    accuracy = sum(r["correct"] for r in rows) / len(rows)
    (HERE / f"{args.out}.json").write_text(json.dumps({"accuracy": accuracy, "rows": rows}, indent=2))
    print(f"\nanswer accuracy: {sum(r['correct'] for r in rows)}/{len(rows)} = {accuracy:.2f}")


if __name__ == "__main__":
    main()
