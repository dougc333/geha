"""Read-only, whole-document TF-IDF search over top-level Docling Markdown files.

This is a lexical baseline for policy discovery. It does not change the table
RAG index or the Streamlit backend.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer


DEFAULT_POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
REVISION_HEADING = re.compile(r"\b(revision|change|update)\s+history\b", re.I)
FRONTMATTER_REVISION = re.compile(r"^\s*(revision date\(s\)|review date)\s*:", re.I)


@dataclass(frozen=True)
class PolicyDocument:
    source_pdf: str
    text: str


@dataclass(frozen=True)
class SearchHit:
    source_pdf: str
    score: float


def _table_cells(line: str) -> list[str]:
    if not line.lstrip().startswith("|"):
        return []
    return [cell.strip().strip("! ").casefold() for cell in line.strip().strip("|").split("|")]


def _is_revision_table_header(line: str) -> bool:
    cells = _table_cells(line)
    return bool(cells) and "date" in cells and any(cell in {"updates", "update", "changes"} for cell in cells)


def without_revision_history(markdown: str) -> str:
    """Drop revision sections and Date/Updates tables, even without a heading."""
    kept: list[str] = []
    revision_heading_level: int | None = None
    in_revision_table = False

    for line in markdown.splitlines():
        heading = HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if revision_heading_level is not None and level <= revision_heading_level:
                revision_heading_level = None
            if REVISION_HEADING.search(heading.group(2)):
                revision_heading_level = level
                continue

        if revision_heading_level is not None:
            continue
        if _is_revision_table_header(line):
            in_revision_table = True
            continue
        if in_revision_table:
            if _table_cells(line) or not line.strip():
                continue
            in_revision_table = False
        if FRONTMATTER_REVISION.match(line):
            continue
        kept.append(line)

    return "\n".join(kept).strip()


def load_policies(directory: Path) -> list[PolicyDocument]:
    """Load only policy files directly in directory; never traverse archives."""
    documents = []
    for path in sorted(directory.glob("geha-coverage-policy-*.docling.md")):
        text = without_revision_history(path.read_text(encoding="utf-8"))
        if text:
            documents.append(
                PolicyDocument(path.name.removesuffix(".docling.md") + ".pdf", text)
            )
    return documents


class TfidfPolicySearch:
    def __init__(self, documents: list[PolicyDocument]):
        if not documents:
            raise ValueError("No nonempty policy documents to index")
        self.documents = documents
        self.vectorizer = TfidfVectorizer(
            lowercase=True, strip_accents="unicode", ngram_range=(1, 2), sublinear_tf=True
        )
        self.matrix = self.vectorizer.fit_transform(
            [f"{doc.source_pdf}\n{doc.text}" for doc in documents]
        )

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_vector = self.vectorizer.transform([query])
        scores = (self.matrix @ query_vector.T).toarray().ravel()
        ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], self.documents[i].source_pdf))
        return [
            SearchHit(self.documents[i].source_pdf, float(scores[i]))
            for i in ranked[:top_k]
            if scores[i] > 0
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Words to look for in complete policy documents")
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    searcher = TfidfPolicySearch(load_policies(args.policy_dir))
    print(f"Indexed {len(searcher.documents)} policy documents (revision history excluded)")
    for hit in searcher.search(args.query, args.top_k):
        print(f"{hit.score:.4f}\t{hit.source_pdf}")


if __name__ == "__main__":
    main()
