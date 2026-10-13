"""Adapter for the existing Docling BM25/vector dental corpus retriever."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from crawl_dir.src.consumer_paths import page_markdown, page_root

CORPUS_PROJECT = REPO / "agentic_search_corpus"
CORPUS_SRC = CORPUS_PROJECT / "src"
GUIDE_DOCUMENT = "fedvip/2026-geha-dental-benefits-guide.pdf"
BROCHURE_DOCUMENT = "fedvip/2026-geha-dental-plan-brochure.pdf"
GUIDE_PAGES = page_root("dental", GUIDE_DOCUMENT, allow_candidate=True)
BROCHURE_PAGES = page_root("dental", BROCHURE_DOCUMENT, allow_candidate=True)


def _document_id(directory_name: str) -> str:
    return re.sub(r"^20\d{2}-|_pages$", "", directory_name).replace("_", "-")


def _section(text: str) -> str:
    match = re.search(r"(?m)^#{1,6}\s+(.+)$", text)
    return re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match.group(1)).strip() if match else "Page content"


@dataclass(frozen=True)
class CorpusHit:
    rank: int
    page: int
    document: str
    source: str
    chunk_id: str
    text: str


class ExistingDentalCorpusRetriever:
    """Reuse agentic_search_corpus without copying its retrieval implementation."""

    def __init__(self, include_plan_brochure: bool = False):
        if str(CORPUS_SRC) not in sys.path:
            sys.path.insert(0, str(CORPUS_SRC))
        from corpus_search import CorpusSearch
        from structured_benefits import StructuredBenefitIndex

        directories = [GUIDE_PAGES]
        if include_plan_brochure:
            directories.append(BROCHURE_PAGES)
        self.search_engine = CorpusSearch(directories=directories, mode="hybrid")
        self.structured_benefits = StructuredBenefitIndex.from_markdown(
            page_markdown("dental", GUIDE_DOCUMENT, 5, allow_candidate=True)
        )

    def search(self, query: str, mode: str = "hybrid", top_k: int = 4) -> list[CorpusHit]:
        documents = self.search_engine.search(query, mode=mode, top_k=top_k)
        return [
            CorpusHit(
                rank=rank,
                page=int(document.metadata["page"]),
                document=str(document.metadata["document"]),
                source=str(document.metadata["source"]),
                chunk_id=str(document.metadata["chunk_id"]),
                text=document.page_content,
            )
            for rank, document in enumerate(documents, start=1)
        ]

    def search_policy_chunks(self, query: str, top_k: int = 4, mode: str = "hybrid"):
        """Return Docling pages in the format consumed by DSPy answer generation.

        CDT questions reserve evidence from an exact-code BM25 lookup before
        broader retrieval. This prevents descriptive wording or chat history
        from pushing the authoritative code-definition page out of the result.
        """
        from policy_qa import PolicyChunk, expand_policy_query

        code_match = re.search(r"\bD\d{4}\b", query, flags=re.IGNORECASE)
        if code_match:
            code = code_match.group(0)
            exact_candidates = self.search(code, mode="bm25", top_k=6)
            # Prefer the page where the code begins its own procedure entry;
            # incidental references to the code can otherwise outrank it.
            exact_hits = [
                hit
                for hit in exact_candidates
                if re.search(rf"(?mi)^\s*\*?{re.escape(code)}\b", hit.text)
            ] or exact_candidates[:1]
            # The benefits-guide comparison table is the canonical compact
            # source for High/Standard in-network member costs across classes.
            comparison_hits = [
                hit
                for hit in self.search(
                    "basic class a intermediate class b major class c high standard in-network you pay",
                    mode="bm25",
                    top_k=6,
                )
                if hit.document.endswith("2026-geha-dental-benefits-guide")
                and hit.page == 5
            ]
            broad_mode = "bm25" if mode == "auto" else mode
            broad_hits = (
                []
                if exact_hits and comparison_hits
                else self.search(expand_policy_query(query), mode=broad_mode, top_k=top_k)
            )
            hits = []
            seen = set()
            for hit in [*exact_hits[:1], *comparison_hits[:1], *broad_hits]:
                identity = (hit.document, hit.page)
                if identity in seen:
                    continue
                seen.add(identity)
                hits.append(hit)
                if len(hits) == top_k:
                    break
        else:
            hits = self.search(expand_policy_query(query), mode=mode, top_k=top_k)
        resolved = self.structured_benefits.resolve(query)
        chunks = []
        for hit in hits:
            text = hit.text
            section = _section(hit.text)
            if resolved and hit.document.endswith("2026-geha-dental-benefits-guide") and hit.page == 5:
                text = resolved.evidence_text()
                section = f"Dental benefit comparison / {resolved.record.benefit_class}"
            year_match = re.search(r"(20\d{2})", hit.document)
            chunks.append(
                PolicyChunk(
                    page=hit.page,
                    text=text,
                    score=1.0 / hit.rank,
                    document_id=_document_id(hit.document),
                    plan_year=int(year_match.group(1)) if year_match else 0,
                    section=section,
                )
            )
        return chunks
