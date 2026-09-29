#!/usr/bin/env python3
"""Add table questions to evals/questions.jsonl from Docling table chunks.

    python evals/generate_table_questions.py [--count 15] [--seed 5]

Reads local_ingest/out/*.jsonl (made by local_ingest/docling_chunks.py), picks
table chunks from different papers, and asks Nova Lite for one question whose
answer is a specific value in the table (a number, setting or name), naming the
model or paper so the question stands alone. A question is kept only if its
evidence value appears verbatim in the table. Gold label: the paper and the
table's page. Questions are appended with ids t01, t02, ... and type "table";
existing t-questions are replaced.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "local_ingest" / "out"
PROMPT = (
    "Here is a table from a research paper. Write ONE question a researcher might ask "
    "whose answer is a specific value in this table (a number, score, setting or name). "
    "Name the model, method or dataset so the question stands alone; don't say 'the "
    "table' or 'this paper'. Reply with JSON only: {\"question\": \"...\", \"answer\": "
    "\"...\", \"evidence\": \"the exact value or cell text copied from the table\"}"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--region", default="us-west-2")
    args = parser.parse_args()
    random.seed(args.seed)

    tables_by_paper: dict[str, list[dict]] = {}
    for path in sorted(OUT.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            chunk = json.loads(line)
            if chunk.get("kind") == "table" and len(chunk["content"]) > 300 and "(part " not in chunk["content"]:
                tables_by_paper.setdefault(chunk["document_id"], []).append(chunk)
    papers = list(tables_by_paper)
    random.shuffle(papers)

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)
    made: list[dict] = []
    for doc_id in papers * 2:
        if len(made) >= args.count:
            break
        table = random.choice(tables_by_paper[doc_id])
        if any(q["document_id"] == doc_id for q in made):
            continue
        response = bedrock.converse(
            modelId="amazon.nova-lite-v1:0",
            system=[{"text": PROMPT}],
            messages=[{"role": "user", "content": [{"text": f"PAPER: {table['title']}\n\nTABLE:\n{table['content']}"}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0.3},
        )
        text = "".join(b.get("text", "") for b in response["output"]["message"]["content"])
        try:
            item = json.loads(text[text.index("{"): text.rindex("}") + 1])
        except ValueError:
            continue
        question, evidence = str(item.get("question", "")).strip(), str(item.get("evidence", "")).strip()
        norm = lambda s: re.sub(r"\s+", " ", s).lower()  # noqa: E731
        if len(evidence) < 1 or norm(evidence) not in norm(table["content"]):
            continue
        if re.search(r"\b(the table|this table|this paper|the paper)\b", question, re.I):
            continue
        made.append({
            "id": f"t{len(made) + 1:02d}", "type": "table", "question": question,
            "answer": str(item.get("answer", "")).strip(), "evidence": evidence,
            "document_id": doc_id, "title": table["title"], "page": table["page_number"], "chunk_id": None,
        })
        print(f"{made[-1]['id']} {table['title'][:40]!r} p{table['page_number']}: {question}  -> {made[-1]['answer']}", flush=True)

    path = HERE / "questions.jsonl"
    kept = [q for q in (json.loads(l) for l in path.read_text().splitlines() if l.strip()) if q["type"] != "table"]
    path.write_text("".join(json.dumps(q) + "\n" for q in kept + made))
    print(f"\n{len(made)} table questions; {len(kept) + len(made)} questions in {path}")


if __name__ == "__main__":
    main()
