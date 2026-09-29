#!/usr/bin/env python3
"""Generate a retrieval eval set from the indexed papers.

    python evals/generate_questions.py [--count 40] [--seed 7]

Samples chunks from different papers (skipping short chunks and reference
lists), and for each asks Nova Lite for one question answerable from that
chunk, a short answer, and an exact evidence quote. A question is kept only if
its quote appears verbatim in the chunk. The gold label is the chunk's paper
and page: retrieval "hits" when it returns any chunk from that page.

Half the questions are "fact" (numbers, names, specific settings) and half
"paraphrase" (concepts asked in different words than the text, which is
harder for keyword search). Output: evals/questions.jsonl.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

import boto3
import psycopg

HERE = Path(__file__).resolve().parent
MODEL = "amazon.nova-lite-v1:0"
PROMPTS = {
    "fact": (
        "Write ONE question that a researcher might ask, answerable only from this passage, "
        "about a specific fact in it: a number, result, name, dataset or setting. Name the "
        "method or model so the question stands alone (don't say 'this paper' or 'the passage')."
    ),
    "paraphrase": (
        "Write ONE conceptual question (how/why/what does X do) answerable from this passage, "
        "using DIFFERENT words than the passage wherever possible: paraphrase its key terms. "
        "Name the method or model so the question stands alone (don't say 'this paper')."
    ),
}
RULES = (
    " Never ask about references, citations, bibliography entries or other cited papers."
    " Avoid vague questions that many pages could answer (\"what role does X play\","
    " \"what approach does X take\"); ask about something specific to this passage."
)
FORMAT = (
    'Reply with JSON only: {"question": "...", "answer": "short answer", '
    '"evidence": "an exact sentence or phrase copied verbatim from the passage that supports the answer"}'
)


def looks_like_references(text: str) -> bool:
    """Reference lists make bad eval pages: bibliography trivia, answerable in many papers."""
    return (bool(re.search(r"\bReferences\b|\bBibliography\b", text))
            or len(re.findall(r"\[\d+\]", text)) > 12
            or len(re.findall(r"\bet al\.", text)) > 3
            or len(re.findall(r"arXiv preprint|In Proceedings|Proc\.|Conference on|Journal of", text)) > 2
            or len(re.findall(r"\b(19|20)\d\d\b", text)) > 10)


# Questions that can't be tested fairly: not standalone, or about citations.
BAD_QUESTION = re.compile(
    r"\b(their|the researchers|this paper|the paper|the passage|the authors|this study|"
    r"references?|cited|citations?|bibliography)\b|et al\.|\[\d+\]", re.IGNORECASE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--replace", default="", help="comma-separated ids to regenerate, keeping the rest")
    args = parser.parse_args()
    replace = [i.strip() for i in args.replace.split(",") if i.strip()]
    kept: list[dict] = []
    if replace:
        existing = [json.loads(l) for l in (HERE / "questions.jsonl").read_text().splitlines() if l.strip()]
        kept = [q for q in existing if q["id"] not in replace]
        todo = [(q["id"], q["type"]) for q in existing if q["id"] in replace]
    else:
        todo = [(f"q{n:02d}", "fact" if n % 2 else "paraphrase") for n in range(1, args.count + 1)]
    random.seed(args.seed)

    url = boto3.client("ssm", region_name=args.region).get_parameter(
        Name="/rag-demo/database-url", WithDecryption=True)["Parameter"]["Value"]
    with psycopg.connect(url) as connection:
        rows = connection.execute(
            """SELECT c.id, c.document_id, d.title, c.page_number, c.content
               FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
               WHERE length(c.content) > 1200"""
        ).fetchall()
    by_doc: dict[str, list] = {}
    for row in rows:
        if not looks_like_references(row[4]):
            by_doc.setdefault(row[1], []).append(row)
    used_docs = {q["document_id"] for q in kept}
    documents = [d for d in by_doc if d not in used_docs] + [d for d in by_doc if d in used_docs]
    random.shuffle(documents)

    bedrock = boto3.client("bedrock-runtime", region_name=args.region)
    out, attempts = [], 0
    for document in documents * 3:  # prefer papers not already in the set
        if len(out) >= len(todo):
            break
        chunk_id, doc_id, title, page, content = random.choice(by_doc[document])
        if any(q["chunk_id"] == chunk_id or q["document_id"] == doc_id for q in kept + out):
            continue
        qid, kind = todo[len(out)]
        attempts += 1
        response = bedrock.converse(
            modelId=MODEL,
            system=[{"text": f"{PROMPTS[kind]}{RULES} {FORMAT}"}],
            messages=[{"role": "user", "content": [{"text": f"PAPER: {title}\n\nPASSAGE:\n{content}"}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0.3},
        )
        text = "".join(b.get("text", "") for b in response["output"]["message"]["content"])
        try:
            item = json.loads(text[text.index("{"): text.rindex("}") + 1])
        except ValueError:
            continue
        if BAD_QUESTION.search(str(item.get("question", ""))):
            continue
        evidence = " ".join(str(item.get("evidence", "")).split())
        if len(evidence) < 15 or evidence.lower() not in " ".join(content.split()).lower():
            continue  # the answer isn't verifiably on this page
        out.append({
            "id": qid, "type": kind, "question": item["question"].strip(),
            "answer": str(item.get("answer", "")).strip(), "evidence": evidence,
            "document_id": doc_id, "title": title, "page": page, "chunk_id": chunk_id,
        })
        print(f"{out[-1]['id']} [{kind:<10}] {title[:40]!r} p{page}: {out[-1]['question']}", flush=True)

    final = sorted(kept + out, key=lambda q: q["id"])
    (HERE / "questions.jsonl").write_text("".join(json.dumps(q) + "\n" for q in final))
    print(f"\n{len(out)} new questions from {attempts} attempts; {len(final)} total -> {HERE / 'questions.jsonl'}")


if __name__ == "__main__":
    main()
