"""Local dental-policy retrieval with DSPy-grounded answer generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

import dspy
from pypdf import PdfReader
from rank_bm25 import BM25Okapi


TOKEN_RE = re.compile(r"[a-z0-9]+")
PAGE_CITATION_RE = re.compile(r"\[p\.\s*(\d+)\]", re.IGNORECASE)
STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "can", "do", "does", "for", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "the", "to", "what",
    "when", "where", "which", "who", "why", "with", "would", "you", "your",
}
QUERY_EXPANSIONS = {
    "glasses": {"eyeglasses", "vision", "frames", "lenses"},
    "eyeglass": {"glasses", "vision", "frames", "lenses"},
    "eyeglasses": {"glasses", "vision", "frames", "lenses"},
    "costco": {"provider", "participating", "location", "network", "in-network"},
    "walmart": {"provider", "participating", "location", "network", "in-network"},
    "target": {"provider", "participating", "location", "network", "in-network"},
    "sams": {"provider", "participating", "location", "network", "in-network"},
    "dentist": {"provider", "participating", "network", "in-network"},
    "optometrist": {"provider", "participating", "vision", "network", "in-network"},
    "contacts": {"vision", "contact", "lenses"},
    "braces": {"orthodontic", "orthodontics"},
}


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _query_tokens(text: str) -> list[str]:
    """Normalize member vocabulary into terms used by the benefits guide."""
    original = [token for token in _tokens(text) if token not in STOP_WORDS]
    expanded = list(original)
    for token in original:
        expanded.extend(QUERY_EXPANSIONS.get(token, ()))
    return expanded


def expand_policy_query(text: str) -> str:
    """Return a retrieval query containing policy vocabulary and user terms."""
    return " ".join(_query_tokens(text))


@dataclass(frozen=True)
class PolicyChunk:
    """A retrievable passage tied to its original PDF page."""

    page: int
    text: str
    score: float = 0.0
    document_id: str = "geha-dental-benefits-guide"
    plan_year: int = 2026
    section: str = "Unspecified section"


def _chunk_page(
    text: str,
    page: int,
    max_chars: int = 1400,
    document_id: str = "geha-dental-benefits-guide",
    plan_year: int = 2026,
) -> list[PolicyChunk]:
    """Create readable, page-bounded chunks without losing citation provenance."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
    paragraphs = [part for part in paragraphs if part]
    chunks: list[PolicyChunk] = []
    current = ""

    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 1 > max_chars:
            chunks.append(PolicyChunk(page=page, text=current, document_id=document_id, plan_year=plan_year))
            current = ""
        if len(paragraph) <= max_chars:
            current = f"{current}\n{paragraph}".strip()
            continue
        for start in range(0, len(paragraph), max_chars):
            piece = paragraph[start : start + max_chars].strip()
            if piece:
                chunks.append(PolicyChunk(page=page, text=piece, document_id=document_id, plan_year=plan_year))

    if current:
        chunks.append(PolicyChunk(page=page, text=current, document_id=document_id, plan_year=plan_year))
    return chunks


def load_policy_chunks(pdf_path: str | Path) -> list[PolicyChunk]:
    """Extract page-aware chunks from one policy PDF."""
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Dental policy PDF not found: {path}")

    year_match = re.search(r"(20\d{2})", path.name)
    plan_year = int(year_match.group(1)) if year_match else 0
    document_id = re.sub(r"^20\d{2}-", "", path.stem)
    chunks: list[PolicyChunk] = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        chunks.extend(
            _chunk_page(
                page.extract_text() or "",
                page_number,
                document_id=document_id,
                plan_year=plan_year,
            )
        )
    if not chunks:
        raise ValueError(f"No searchable text could be extracted from {path}")
    return chunks


class DentalPolicyIndex:
    """Small local BM25 index scoped to a single dental policy document."""

    def __init__(self, chunks: Iterable[PolicyChunk]):
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("At least one policy chunk is required")
        self._bm25 = BM25Okapi([_tokens(chunk.text) for chunk in self.chunks])

    @classmethod
    def from_pdf(cls, pdf_path: str | Path) -> "DentalPolicyIndex":
        return cls(load_policy_chunks(pdf_path))

    def search(self, query: str, top_k: int = 4) -> list[PolicyChunk]:
        query_tokens = _query_tokens(query)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        query_terms = set(query_tokens)
        candidates = [
            (index, score, len(query_terms.intersection(_tokens(chunk.text))))
            for index, (chunk, score) in enumerate(zip(self.chunks, scores))
        ]
        # A positive BM25 score is not a safe relevance gate: IDF can be
        # negative in tiny corpora. Require lexical overlap, then use overlap
        # and BM25 together for stable ranking.
        ranked = sorted(
            (item for item in candidates if item[2] > 0),
            key=lambda item: (item[2], item[1]),
            reverse=True,
        )
        return [
            PolicyChunk(
                page=self.chunks[index].page,
                text=self.chunks[index].text,
                score=float(score),
                document_id=self.chunks[index].document_id,
                plan_year=self.chunks[index].plan_year,
                section=self.chunks[index].section,
            )
            for index, score, _ in ranked[:top_k]
        ]


class AnswerDentalPolicyQuestion(dspy.Signature):
    """Answer using only the supplied GEHA dental-policy evidence.

    Cite every material statement with the page marker from the evidence, using
    the exact form ``[p. N]``. If the evidence does not answer the question,
    say that the answer was not found in the supplied document. You may state
    that a service is listed as covered and report its documented copay,
    coinsurance, limit, or exclusion when the evidence supports it. Phrase these
    as plan terms, not as a prediction that an individual claim will be approved
    or paid. Do not infer enrollment eligibility or give medical advice.

    When the question names a store, dentist, or other provider that is not
    named in the evidence, still explain any relevant general benefit found in
    the evidence. Then state separately that the document does not establish
    whether that specific provider participates; never turn provider-specific
    uncertainty into “the benefit was not found.”
    """

    question: str = dspy.InputField(desc="The member's dental policy question.")
    conversation: str = dspy.InputField(desc="Recent conversation for resolving follow-up references.")
    evidence: str = dspy.InputField(desc="Retrieved passages labeled with their source PDF page.")
    revision: str = dspy.InputField(
        desc="Correction instructions for a prior draft, or 'No revision requested.'"
    )
    answer: str = dspy.OutputField(desc="A concise grounded answer with inline [p. N] citations.")


def _evidence_text(chunks: list[PolicyChunk]) -> str:
    return "\n\n".join(
        "[source: "
        f"document_id={chunk.document_id}; plan_year={chunk.plan_year}; "
        f"page={chunk.page}; section={chunk.section}; citation=[p. {chunk.page}]]\n"
        f"{chunk.text}"
        for chunk in chunks
    )


class DentalPolicyQA:
    """Retrieve locally, then use a DSPy program to synthesize the answer."""

    def __init__(self, index: DentalPolicyIndex, program: Any | None = None):
        self.index = index
        self.program = program or dspy.ChainOfThought(AnswerDentalPolicyQuestion)

    def ask(
        self,
        question: str,
        conversation: str = "",
        top_k: int = 4,
        retrieve: Callable[[str, int], list[PolicyChunk]] | None = None,
        retrieval_query: str | None = None,
    ) -> tuple[str, list[PolicyChunk]]:
        search_text = retrieval_query or f"{conversation}\n{question}".strip()
        chunks = (retrieve or self.index.search)(search_text, top_k)
        if not chunks:
            return "I couldn't find relevant information in the dental benefits guide.", []

        return self._generate(
            question,
            conversation,
            chunks,
            revision="No revision requested.",
        ), chunks

    def revise(
        self,
        question: str,
        prior_answer: str,
        critique: str,
        chunks: list[PolicyChunk],
        conversation: str = "",
    ) -> str:
        """Regenerate once from the same evidence after a grounding failure."""
        revision = (
            "The previous draft was rejected by the grounding guard. Rewrite it using only "
            "the supplied evidence, preserving supported facts and citations while removing "
            f"the unsupported claim. Guard feedback: {critique}\n\n"
            f"Previous draft:\n{prior_answer}\n\n"
            "Do not speculate that a named provider participates or does not participate. "
            "When the evidence does not identify that provider, say only that the supplied "
            "document does not establish its participation."
        )
        return self._generate(question, conversation, chunks, revision=revision)

    def _generate(
        self,
        question: str,
        conversation: str,
        chunks: list[PolicyChunk],
        revision: str,
    ) -> str:
        """Generate and citation-check an answer from an already assembled context."""

        prediction = self.program(
            question=question,
            conversation=conversation or "No earlier conversation.",
            evidence=_evidence_text(chunks),
            revision=revision,
        )
        answer = str(getattr(prediction, "answer", "")).strip()
        if not answer:
            return "I couldn't produce an answer from the retrieved policy evidence."

        allowed_pages = {chunk.page for chunk in chunks}
        cited_pages = {int(page) for page in PAGE_CITATION_RE.findall(answer)}
        invalid_pages = cited_pages - allowed_pages
        if invalid_pages:
            return "I couldn't verify the generated answer's citations against the retrieved policy pages."
        missing_retrieved_pages = allowed_pages - cited_pages
        if missing_retrieved_pages:
            pages = ", ".join(
                f"[p. {page}]" for page in sorted(missing_retrieved_pages)
            )
            answer = f"{answer}\n\nAdditional retrieved source pages: {pages}"
        return answer
