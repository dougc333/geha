"""Build instruction and chain-of-thought SFT data for the GEHA answer generator.

Each QA pair becomes two chat examples, mirroring the two data formats used in
multi-task instruction finetuning (Chung et al., arXiv 2210.11416):

* ``direct``: retrieved passages + question -> answer.
* ``cot``: retrieved passages + question -> cited evidence, then the answer.

The passages are the gold reference contexts mixed with distractor chunks from
the same split, so the model learns to ignore irrelevant retrieval results
(the RAFT recipe). The chain-of-thought rationale is extractive: it quotes the
gold sentences that best overlap the reference answer. No model call is made.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

try:
    from .prepare_retriever_splits import read_jsonl, write_jsonl
except ImportError:  # Permit direct execution from finetuning/.
    from prepare_retriever_splits import read_jsonl, write_jsonl


DATA_DIR = Path(__file__).resolve().parent / "data"
QA_FILES = {
    "train": "train/qa_pairs.jsonl",
    "validation": "validation/qa_pairs.jsonl",
    "test": "test/qa_pairs.filtered-existing.jsonl",
}

SYSTEM_PROMPT = (
    "You are a GEHA dental benefits assistant. Answer using only the numbered "
    "passages. Some passages are irrelevant; ignore them. If the passages do "
    "not contain the answer, say so."
)
DIRECT_INSTRUCTION = "Answer the question concisely."
COT_INSTRUCTION = (
    "Reason step by step. First list the supporting evidence as quoted "
    "sentences with their passage numbers, then give the answer.\n"
    "Format:\nEvidence:\n- [n] \"quote\"\nAnswer: <answer>"
)

STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i if in is it "
    "its my of on or that the their there these they this to was what when "
    "where which who will with you your".split()
)
MIN_DISTRACTOR_CHARS = 100


def content_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9$%.\-]+", text.lower())
        if token.strip(".-") and token not in STOPWORDS
    ]


def strip_header(context: str) -> str:
    """Drop the ``document | pages | section`` line contextualized chunks start with."""
    head, separator, body = context.partition("\n\n")
    return body if separator and " | pages " in head else context


def evidence_sentences(
    passages: list[tuple[int, str]], answer: str, *, limit: int = 2
) -> list[tuple[int, str]]:
    """Return the gold sentences that cover the most answer tokens."""
    answer_tokens = set(content_tokens(answer))
    scored: list[tuple[float, int, int, str]] = []
    seen: set[str] = set()
    for number, text in passages:
        for position, sentence in enumerate(
            re.split(r"(?<=[.!?])\s+|\n+", strip_header(text))
        ):
            sentence = sentence.strip(" +-•\t")
            if len(sentence) < 15 or sentence in seen:
                continue
            seen.add(sentence)
            overlap = len(answer_tokens & set(content_tokens(sentence)))
            if overlap:
                scored.append((-overlap, number, position, sentence))
    scored.sort()
    chosen = sorted(scored[:limit], key=lambda item: (item[1], item[2]))
    return [(number, sentence) for _, number, _, sentence in chosen]


def build_passages(
    row: dict[str, Any],
    chunks: list[dict[str, Any]],
    *,
    distractors: int,
    rng: random.Random,
) -> tuple[list[str], list[int]]:
    gold_ids = set(row.get("source_chunk_ids") or [])
    pool = [
        chunk
        for chunk in chunks
        if chunk["chunk_id"] not in gold_ids
        and len(chunk.get("text") or "") >= MIN_DISTRACTOR_CHARS
    ]
    picked = rng.sample(pool, min(distractors, len(pool)))
    items = [(text, True) for text in row["reference_contexts"]] + [
        (chunk.get("contextualized_text") or chunk["text"], False) for chunk in picked
    ]
    rng.shuffle(items)
    texts = [text for text, _ in items]
    gold_numbers = [index + 1 for index, (_, gold) in enumerate(items) if gold]
    return texts, gold_numbers


def user_message(passages: list[str], question: str, instruction: str) -> str:
    numbered = "\n\n".join(
        f"[{number}] {text.strip()}" for number, text in enumerate(passages, start=1)
    )
    return f"Passages:\n{numbered}\n\nQuestion: {question}\n\n{instruction}"


def cot_target(evidence: list[tuple[int, str]], answer: str) -> str:
    lines = ["Evidence:"] + [f'- [{number}] "{sentence}"' for number, sentence in evidence]
    return "\n".join(lines) + f"\nAnswer: {answer}"


def build_examples(
    rows: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    distractors: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    examples: list[dict[str, Any]] = []
    for row in rows:
        passages, gold_numbers = build_passages(
            row, chunks, distractors=distractors, rng=rng
        )
        evidence = evidence_sentences(
            [(number, passages[number - 1]) for number in gold_numbers],
            row["answer"],
        )
        targets = {"direct": (DIRECT_INSTRUCTION, row["answer"])}
        # Skip the CoT copy when no gold sentence overlaps the answer, rather
        # than training on an empty or unsupported rationale.
        if evidence:
            targets["cot"] = (COT_INSTRUCTION, cot_target(evidence, row["answer"]))
        for task, (instruction, target) in targets.items():
            examples.append(
                {
                    "id": f"{row['id']}-{task}",
                    "qa_id": row["id"],
                    "task": task,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": user_message(passages, row["question"], instruction),
                        },
                        {"role": "assistant", "content": target},
                    ],
                    "reference_answer": row["answer"],
                    "gold_passages": gold_numbers,
                }
            )
    return examples


def prepare(data_dir: Path, *, distractors: int, seed: int) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for offset, (split, qa_file) in enumerate(QA_FILES.items()):
        rows = read_jsonl(data_dir / qa_file)
        chunks = read_jsonl(data_dir / split / "chunks.jsonl")
        examples = build_examples(
            rows, chunks, distractors=distractors, seed=seed + offset
        )
        write_jsonl(data_dir / split / "generator_sft.jsonl", examples)
        summary[split] = {
            task: sum(example["task"] == task for example in examples)
            for task in ("direct", "cot")
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--distractors", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = prepare(args.data_dir, distractors=args.distractors, seed=args.seed)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
