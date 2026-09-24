"""Evaluate the same 13 preference-row questions used by naive_chroma."""

import json
import re
import unicodedata
from collections import Counter

from rag import ROOT, Retriever

GOLD_PATH = ROOT / "evals" / "preference_rows.json"
RESULT_JSON = ROOT / "evals" / "preference_row_results.json"
RESULT_MD = ROOT / "evals" / "preference_row_results.md"
README_START = "<!-- PREFERENCE_ROW_EVAL_START -->"
README_END = "<!-- PREFERENCE_ROW_EVAL_END -->"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", value))


def verified_row(table_text: str, case: dict) -> bool:
    """Require the gold values to occur together in one Markdown table row."""
    for line in table_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        preference, prior_auth, drug, code = cells[:4]
        if (
            normalize(preference) == normalize(case["preference"])
            and normalize(prior_auth) == normalize(case["prior_auth"])
            and normalize(drug) == normalize(case["drug_name"])
            and normalize(code) == normalize(case["hcpcs_code"])
        ):
            return True
    return False


def run() -> dict:
    cases = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    retriever = Retriever()
    chunks = {chunk["id"]: chunk for chunk in retriever.chunks}
    results = []
    for case in cases:
        gold_id = case["gold_chunk_id"]
        if gold_id not in chunks:
            raise ValueError(f"Gold chunk missing: {gold_id}")
        gold = chunks[gold_id]
        if gold["metadata"]["kind"] != "table" or gold["metadata"]["source_file"] != case["source_pdf"]:
            raise ValueError(f"Gold chunk is not the source table: {gold_id}")
        if not verified_row(gold["text"], case):
            raise ValueError(f"Gold drug/preference/auth/code are not in one table row: {case['id']}")

        hits = retriever.search(case["query"], k=len(chunks), document="all")
        rank = next((index for index, hit in enumerate(hits, 1) if hit["id"] == gold_id), None)
        top = hits[0] if hits else None
        results.append({
            **case,
            "gold_row_verified": True,
            "gold_rank": rank,
            "hit_at_1": rank == 1,
            "hit_at_4": rank is not None and rank <= 4,
            "top_1_id": top["id"] if top else None,
            "top_1_kind": top["metadata"]["kind"] if top else None,
            "top_1_source": top["metadata"]["source_file"] if top else None,
            "top_1_has_exact_gold_row": verified_row(top["text"], case) if top else False,
            "miss_reason": (
                "A billing table with the drug and code but no preference column ranked above the preference table."
                if rank != 1 and top and top["metadata"]["kind"] == "table"
                and "| Preference |" not in top["text"]
                else None if rank == 1 else "Another chunk ranked above the gold preference table."
            ),
            "retrieved_ids": [hit["id"] for hit in hits[:4]],
        })

    by_preference = {}
    for preference in ("preferred", "non-preferred"):
        subset = [row for row in results if row["preference"] == preference]
        by_preference[preference] = {
            "questions": len(subset),
            "hit_at_1": sum(row["hit_at_1"] for row in subset),
            "hit_at_4": sum(row["hit_at_4"] for row in subset),
        }
    summary = {
        "questions": len(results),
        "indexed_pdfs": len({chunk["metadata"]["source_file"] for chunk in chunks.values()}),
        "indexed_chunks": len(chunks),
        "verified_gold_rows": sum(row["gold_row_verified"] for row in results),
        "hit_at_1": sum(row["hit_at_1"] for row in results),
        "hit_at_4": sum(row["hit_at_4"] for row in results),
        "by_preference": by_preference,
        "top_1_kinds": dict(Counter(row["top_1_kind"] for row in results)),
    }
    return {"summary": summary, "results": results}


def markdown(report: dict) -> str:
    summary = report["summary"]
    total = summary["questions"]
    lines = [
        "# RAG_demo preference-row retrieval evaluation", "",
        "The 13 questions are copied verbatim from the naive_chroma gold question set.",
        "This test searches both indexed PDFs using the same hybrid retriever as the Streamlit app.",
        "Before scoring, it confirms that the drug, preference, prior authorization, and HCPCS code",
        "occur together in one Markdown table row. A hit then means the complete table chunk was retrieved;",
        "it does not measure generated-answer correctness.", "",
        f"- Indexed: **{summary['indexed_pdfs']} PDFs**, **{summary['indexed_chunks']} chunks**.",
        f"- Verified gold table rows: **{summary['verified_gold_rows']}/{total}**.",
        f"- Table hit@1: **{summary['hit_at_1']}/{total}** ({summary['hit_at_1']/total:.1%}).",
        f"- Table hit@4: **{summary['hit_at_4']}/{total}** ({summary['hit_at_4']/total:.1%}).",
        "", "| Preference | Questions | Hit@1 | Hit@4 |", "|---|---:|---:|---:|",
    ]
    for preference, stats in summary["by_preference"].items():
        lines.append(f"| {preference} | {stats['questions']} | {stats['hit_at_1']} | {stats['hit_at_4']} |")
    lines.extend([
        "", "| ID | Question | Gold answer | Gold table chunk | Top result | Gold rank | Top-1 diagnosis |",
        "|---|---|---|---|---|---:|---|",
    ])
    for row in report["results"]:
        values = [
            row["id"], row["query"], row["expected_answer"], row["gold_chunk_id"],
            row["top_1_id"] or "None", str(row["gold_rank"] or "—"),
            row["miss_reason"] or "Exact gold row is in the first table chunk.",
        ]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    lines.extend([
        "", "## Which retrieval ranked better, and why?", "",
        "On these 13 questions, naive Chroma ranked its labeled chunk first **13/13** times,",
        "while RAG_demo ranked the complete preference table first **12/13** times. Thus naive",
        "Chroma had one more top-1 hit; both found the labeled evidence within four results for",
        "all 13 questions. The RAG_demo miss was Vegzelma: its page-3 billing table mentions",
        "Vegzelma and Q5129 but has no preference column, and ranked above the page-1 preference table.",
        "That is the observed ranking error, not proof that whole-table chunks are inherently worse.", "",
        "RAG_demo preserves each drug, preference, prior authorization, and code in one Markdown",
        "table row under explicit column headers. The naive word chunk happened to contain those",
        "rows, but it does not encode their row/column structure. This difference matters for",
        "interpreting evidence, which these retrieval scores do not measure.", "",
        "The naive run searched 32 PDFs with pure vector ranking. RAG_demo searched two PDFs",
        "with combined vector and keyword ranking, so this is not a controlled chunking ablation.",
        "Neither score tests generated-answer correctness.", "",
    ])
    return "\n".join(lines)


def update_readme(report: dict) -> None:
    readme = ROOT / "README.md"
    current = readme.read_text(encoding="utf-8")
    section = re.sub(r"^(#{1,2})(?= )", r"##\1", markdown(report), flags=re.MULTILINE)
    block = f"{README_START}\n{section}\n{README_END}"
    if README_START not in current or README_END not in current:
        raise ValueError("README is missing preference evaluation markers")
    before, rest = current.split(README_START, 1)
    _, after = rest.split(README_END, 1)
    readme.write_text(before.rstrip() + "\n\n" + block + after, encoding="utf-8")


if __name__ == "__main__":
    report = run()
    RESULT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RESULT_MD.write_text(markdown(report), encoding="utf-8")
    update_readme(report)
    print(json.dumps(report["summary"], indent=2))
