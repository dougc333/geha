"""Evaluate row-level preference questions against the existing plain-chunk Chroma index.

The fixed gold file is curated separately. A hit requires a chunk with the row's
preference evidence, not merely any chunk from the same PDF or a billing mention.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from index import DEFAULT_DB_DIR, open_index, search

ROOT = Path(__file__).resolve().parent


def format_hit(hit: dict) -> str:
    meta = hit["metadata"]
    return f"{meta['source_file']} p{meta['page']} c{meta['chunk']}"


def explain_miss(case: dict, top: dict | None) -> str:
    if not case["gold_chunk_ids"]:
        return case.get("unindexed_reason", "The source row has no indexed chunk.")
    if top is None:
        return "Search returned no chunks."
    meta = top["metadata"]
    text = top["text"].lower()
    anchor = case["row_anchor"].lower()
    code = case["hcpcs_code"].lower()
    if meta["source_file"] != case["source_pdf"]:
        if "short-acting-gcsfs" in meta["source_file"] and "long-acting-gcsfs" in case["source_pdf"]:
            return "The short-acting G-CSF table's similar preference language outranked the long-acting drug row."
        if anchor in text:
            return f"A mention of {anchor} in another policy outranked the source table row."
        return "An unrelated policy chunk outranked the source table row; semantic similarity favored broad policy wording."
    if meta["page"] != case["source_page"]:
        if anchor in text or code in text:
            return "Another mention of the drug or code elsewhere in the right PDF outranked its preference table."
        return "General prose in the right PDF outranked the preference table."
    if meta["chunk"] in {int(g.rsplit("-c", 1)[-1]) - 1 for g in case["gold_chunk_ids"]} | {
        int(g.rsplit("-c", 1)[-1]) + 1 for g in case["gold_chunk_ids"]
    }:
        return "An adjacent fixed-size chunk from the same table page outranked the chunk containing this row."
    return "A different chunk on the right page outranked the chunk containing this row."


def evaluate(cases: list[dict], collection) -> dict:
    results = []
    corpus_size = collection.count()
    indexed = collection.get(include=["metadatas"])
    indexed_ids = set(indexed["ids"])
    missing = [(case["id"], chunk) for case in cases for chunk in case["gold_chunk_ids"] if chunk not in indexed_ids]
    if missing:
        raise ValueError(f"Gold chunks missing from this index: {missing[:5]}")
    for index, case in enumerate(cases, 1):
        hits = search(collection, case["query"], k=corpus_size)
        gold = set(case["gold_chunk_ids"])
        rank = next((i for i, hit in enumerate(hits, 1) if hit["id"] in gold), None)
        source_rank = next(
            (i for i, hit in enumerate(hits, 1) if hit["metadata"]["source_file"] == case["source_pdf"]),
            None,
        )
        top = hits[0] if hits else None
        row = {key: value for key, value in case.items() if key != "mapping_diagnostics"}
        row.update(
            gold_rank=rank,
            source_rank=source_rank,
            top1=(
                {
                    "id": top["id"],
                    "source_file": top["metadata"]["source_file"],
                    "page": top["metadata"]["page"],
                    "chunk": top["metadata"]["chunk"],
                    "distance": round(top["distance"], 4),
                    "excerpt": top["text"][:280],
                }
                if top else None
            ),
            error_reason=None if rank == 1 else explain_miss(case, top),
        )
        results.append(row)
        if index % 20 == 0:
            print(f"Evaluated {index}/{len(cases)} questions", flush=True)
    ranks = [r["gold_rank"] for r in results if r["gold_rank"] is not None]
    indexable_rows = sum(bool(r["gold_chunk_ids"]) for r in results)
    def group_stats(group):
        return {
            "queries": len(group),
            "hit_at_1": sum(r["gold_rank"] == 1 for r in group),
            "hit_at_4": sum(r["gold_rank"] is not None and r["gold_rank"] <= 4 for r in group),
        }
    summary = {
        "questions": len(results),
        "policies": len({r["source_pdf"] for r in results}),
        "indexed_chunks": corpus_size,
        "indexed_pdfs": len({m["source_file"] for m in indexed["metadatas"]}),
        "indexable_gold_rows": indexable_rows,
        "unindexed_gold_rows": len(results) - indexable_rows,
        "row_hit_at_1": sum(r is not None and r <= 1 for r in ranks),
        "row_hit_at_4": sum(r is not None and r <= 4 for r in ranks),
        "row_hit_at_10": sum(r is not None and r <= 10 for r in ranks),
        "row_hit_anywhere": len(ranks),
        "source_hit_at_1": sum(r["source_rank"] == 1 for r in results),
        "mrr": round(sum(1 / r for r in ranks) / len(results), 4),
        "miss_categories": dict(Counter(
            "source page not indexed" if not r["gold_chunk_ids"]
            else "other policy" if r["top1"]["source_file"] != r["source_pdf"]
            else "other page" if r["top1"]["page"] != r["source_page"]
            else "same page wrong chunk"
            for r in results if r["gold_rank"] != 1 and r["top1"]
        )),
        "by_preference": {
            pref: group_stats([r for r in results if r["preference"] == pref])
            for pref in ("preferred", "non-preferred")
        },
        "by_policy": {
            pdf: group_stats([r for r in results if r["source_pdf"] == pdf])
            for pdf in sorted({r["source_pdf"] for r in results})
        },
    }
    return {"summary": summary, "results": results}


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Plain-chunk Chroma: preferred-row retrieval evaluation", "",
        "Each question asks for one row's preference, HCPCS code, and prior authorization. "
        "The gold result is a page-1 chunk containing the row's preference evidence; "
        "a billing or revision mention is not counted. Searches use the app's unfiltered "
        "Chroma vector query across 32 policy PDFs. No Tesseract or other OCR is used, so pages without "
        "embedded text contribute no chunks. The other 15 PDFs have no qualifying "
        "preference rows but remain searchable distractors where text exists. "
        "No answer model was evaluated.", "",
        f"- Gold rows: **{s['questions']}** across **{s['policies']}** preference-table PDFs.",
        f"- Rows without an indexed source table: **{s['unindexed_gold_rows']}**; "
        f"retrievable row gold: **{s['indexable_gold_rows']}**.",
        f"- Strict row hit@1: **{s['row_hit_at_1']}/{s['questions']}** "
        f"({s['row_hit_at_1']/s['questions']:.1%}); hit@4: **{s['row_hit_at_4']}/{s['questions']}** "
        f"({s['row_hit_at_4']/s['questions']:.1%}); hit@10: **{s['row_hit_at_10']}/{s['questions']}** "
        f"({s['row_hit_at_10']/s['questions']:.1%}).",
        f"- Correct PDF at rank 1: **{s['source_hit_at_1']}/{s['questions']}** "
        f"({s['source_hit_at_1']/s['questions']:.1%}); MRR: **{s['mrr']:.3f}**.",
        f"- Other-policy top-1 misses: {s['miss_categories'].get('other policy',0)}; "
        f"same-policy other-page misses: {s['miss_categories'].get('other page',0)}; "
        f"same-page wrong-chunk misses: {s['miss_categories'].get('same page wrong chunk',0)}; "
        f"source-page-not-indexed misses: {s['miss_categories'].get('source page not indexed',0)}.",
        "", "## Breakdown", "",
        "| Preference | Rows | Hit@1 | Hit@4 |", "|---|---:|---:|---:|",
    ]
    for pref, stats in s["by_preference"].items():
        lines.append(f"| {pref} | {stats['queries']} | {stats['hit_at_1']} | {stats['hit_at_4']} |")
    lines.extend(["", "| Policy PDF | Rows | Hit@1 | Hit@4 |", "|---|---:|---:|---:|"])
    for policy, stats in s["by_policy"].items():
        lines.append(f"| {policy} | {stats['queries']} | {stats['hit_at_1']} | {stats['hit_at_4']} |")
    lines.extend(["", "## Per-row questions and results", ""])
    previous = None
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    for index, row in enumerate(report["results"]):
        if row["source_pdf"] != previous:
            previous = row["source_pdf"]
            lines.extend([
                f"### {previous}", "",
                "| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |",
                "|---|---|---|---|---|---:|---|",
            ])
        chunks=", ".join(f"p{row['source_page']} c{int(x.rsplit('-c',1)[-1])}" for x in row['gold_chunk_ids']) or f"No chunk (page {row['source_page']} lacks embedded text)"
        top=row["top1"]
        first_hit=(f"{top['source_file']} p{top['page']} c{top['chunk']}" if top else "No result")
        diagnosis=(f"{first_hit}. Correct row." if row["gold_rank"] == 1 else
                   f"{first_hit}. {row['error_reason']}")
        lines.append(
            f"| {cell(row['id'])} | {cell(row['query'])} | {cell(row['expected_answer'])} "
            f"| {cell(chunks)} | {'Yes' if row['gold_rank'] == 1 else 'No'} "
            f"| {row['gold_rank'] if row['gold_rank'] is not None else '—'} "
            f"| {cell(diagnosis)} |"
        )
        if index == len(report["results"])-1 or report["results"][index+1]["source_pdf"] != previous:
            lines.append("")
    lines.extend([
        "## Interpretation", "",
        "A top-1 miss measures retrieval only. The answer text above is the source-table gold label, "
        "not a claim that the search UI generated a correct answer. Fixed word chunks can put "
        "multiple preference rows together, split a row near a boundary, or rank a billing "
        "mention ahead of its preference table. Miss reasons describe the observed first hit "
        "and the likely ranking failure; they cannot establish the embedding model's internal cause. "
        "The gold file records every accepted chunk ID.", "",
        "The questions explicitly name a policy. Scores apply to these exact questions: the shorter "
        "`Is Treanda preferred?` query, for example, previously placed its table chunk fifth.", "",
        "Gold labels were originally seeded from legacy CSV preference tables; runtime table ingestion now uses reviewed HTML. "
        "cross-checked against the plain index's page-1 drug and code text where available. "
        "Datroway's two gold rows have no indexed page-1 text. Retain the "
        "source PDFs as the authority if a PDF is later revised.", "",
    ])
    return "\n".join(lines)


START = "<!-- PREFERENCE_ROW_EVAL_START -->"
END = "<!-- PREFERENCE_ROW_EVAL_END -->"


def update_readme(readme: Path, report: dict) -> None:
    current = readme.read_text() if readme.exists() else "# GEHA plain-chunk Chroma search\n"
    section = re.sub(
        r"^(#{1,3})(?= )", lambda match: "#" + match.group(1),
        markdown(report), flags=re.MULTILINE,
    )
    block = f"{START}\n{section}\n{END}"
    if START in current and END in current:
        prefix, remaining = current.split(START, 1)
        _, suffix = remaining.split(END, 1)
        updated = prefix.rstrip() + "\n\n" + block + suffix
    else:
        updated = current.rstrip() + "\n\n" + block + "\n"
    readme.write_text(updated)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, default=ROOT / "gold_preference_rows.json")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--out-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    cases = json.loads(args.gold.read_text())
    report = evaluate(cases, open_index(args.db_dir))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "preference_row_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    update_readme(args.out_dir / "README.md", report)
    print(json.dumps(report["summary"], indent=2))
