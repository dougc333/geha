"""Pure ranking and citation helpers for the GEHA query service."""

from __future__ import annotations


def reciprocal_rank_fusion(*ranked_lists: list[dict], rank_constant: int = 60) -> list[dict]:
    combined: dict[int, dict] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, start=1):
            chunk_id = int(row["id"])
            item = combined.setdefault(chunk_id, {**row, "score": 0.0})
            item["score"] += 1.0 / (rank_constant + rank)
    return sorted(combined.values(), key=lambda row: (-row["score"], row["id"]))


def evidence_prompt(question: str, rows: list[dict]) -> tuple[str, list[dict]]:
    citations = []
    blocks = []
    for number, row in enumerate(rows, start=1):
        citation = {
            "number": number,
            "title": row["title"],
            "page": row["page_number"],
            "source": row["source"],
            "relative_path": row["relative_path"],
        }
        citations.append(citation)
        blocks.append(
            f"[{number}] {row['title']} — page {row['page_number']}\n{row['content']}"
        )
    prompt = (
        "Answer the GEHA benefits or coverage question using only the supplied evidence. "
        "Cite factual claims with bracketed source numbers such as [1]. If the evidence "
        "does not answer the question, say so. Do not infer eligibility or make a coverage "
        "determination for a specific member.\n\n"
        f"QUESTION:\n{question}\n\nEVIDENCE:\n" + "\n\n".join(blocks)
    )
    return prompt, citations
