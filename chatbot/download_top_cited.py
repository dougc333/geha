#!/usr/bin/env python3
"""Download the most-cited ML/AI papers on arXiv, with a metadata JSON next to each PDF.

    python download_top_cited.py                 # 300 papers
    python download_top_cited.py --count 50 --out /tmp/papers

1. Ranking: Semantic Scholar bulk search, sorted by citation count, over
   Computer Science papers matching core ML terms (see QUERIES). Only papers
   with a new-style arXiv ID are kept, since the PDF comes from arXiv.
2. Topic filter: arXiv metadata (fetched in batches of 100) must list an ML/AI
   category (cs.LG, cs.AI, cs.CL, cs.CV, cs.NE, cs.IR, stat.ML, ...).
3. Download: PDFs from export.arxiv.org, 3 s apart as arXiv asks of scripts.

Each paper gets <arxiv_id>.pdf and <arxiv_id>.json. The JSON has the same
fields as aws_rag's sidecars (so the pipeline can ingest them unchanged) plus
citation_count, rank and semantic_scholar_id. manifest.json lists the ranking.
Re-running resumes: existing PDFs are skipped.

Citation counts are Semantic Scholar's, and "ML/AI" is approximated by the
query terms plus arXiv categories, so a famous paper whose title and abstract
avoid every query term can be missed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "aws_rag" / "query"))
import arxiv_meta  # noqa: E402  (shared with the aws_rag pipeline)

S2_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
QUERIES = [  # each query returns up to 1,000 papers per page, most-cited first
    '"neural network" | "deep learning" | "machine learning" | "language model" | '
    '"reinforcement learning" | transformer | convolutional | attention | embedding | generative',
    'optimization | gradient | stochastic | classification | detection | segmentation | '
    'recognition | adversarial | diffusion | "graph neural" | "representation learning"',
]
ML_CATEGORIES = {"cs.LG", "cs.AI", "cs.CL", "cs.CV", "cs.NE", "cs.IR", "cs.RO", "cs.MA",
                 "cs.SD", "eess.AS", "eess.IV", "stat.ML"}
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "agentic_search" / "data" / "arxiv_top300"


def get_json(url: str) -> dict:
    for attempt in range(5):
        try:
            return json.loads(arxiv_meta.fetch(url, 50 << 20, timeout=60))
        except Exception as exc:  # Semantic Scholar rate-limits unauthenticated clients (429)
            wait = 5 * (attempt + 1)
            print(f"  retry in {wait}s ({exc})", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"giving up on {url}")


def ranked_candidates(pages_per_query: int) -> list[dict]:
    """Semantic Scholar papers with arXiv IDs, most-cited first, deduplicated."""
    papers: dict[str, dict] = {}
    for query in QUERIES:
        token = None
        for _ in range(pages_per_query):
            params = {"query": query, "fieldsOfStudy": "Computer Science",
                      "sort": "citationCount:desc",
                      "fields": "title,citationCount,year,externalIds"}
            if token:
                params["token"] = token
            page = get_json(f"{S2_URL}?{urllib.parse.urlencode(params)}")
            for paper in page.get("data", []):
                arxiv_id = arxiv_meta.find_arxiv_id((paper.get("externalIds") or {}).get("ArXiv") or "")
                if arxiv_id and arxiv_id not in papers:
                    papers[arxiv_id] = {"arxiv_id": arxiv_id, "citation_count": paper.get("citationCount") or 0,
                                        "semantic_scholar_id": paper["paperId"], "s2_title": paper["title"]}
            token = page.get("token")
            time.sleep(2)
            if not token:
                break
    return sorted(papers.values(), key=lambda p: -p["citation_count"])


def arxiv_batch(ids: list[str]) -> dict[str, dict]:
    """arXiv metadata for up to 100 IDs in one API call, keyed by version-less ID."""
    url = ("https://export.arxiv.org/api/query?" +
           urllib.parse.urlencode({"id_list": ",".join(ids), "max_results": len(ids)}))
    feed = ET.fromstring(arxiv_meta.fetch(url, 20 << 20, timeout=60))
    found = {}
    for entry in feed.findall("a:entry", arxiv_meta.NS):
        arxiv_id = arxiv_meta.find_arxiv_id(entry.findtext("a:id", "", arxiv_meta.NS))
        title = " ".join(entry.findtext("a:title", "", arxiv_meta.NS).split())
        if not arxiv_id or title == "Error":
            continue
        primary = entry.find("arxiv:primary_category", arxiv_meta.NS)
        text = lambda tag: " ".join((entry.findtext(tag, "", arxiv_meta.NS) or "").split()) or None  # noqa: E731
        found[arxiv_id.split("v")[0]] = {
            "arxiv_id": arxiv_id.split("v")[0],
            "title": title,
            "authors": [" ".join(a.findtext("a:name", "", arxiv_meta.NS).split())
                        for a in entry.findall("a:author", arxiv_meta.NS)],
            "published": (entry.findtext("a:published", "", arxiv_meta.NS) or "")[:10] or None,
            "updated": (entry.findtext("a:updated", "", arxiv_meta.NS) or "")[:10] or None,
            "abstract": text("a:summary"),
            "primary_category": primary.get("term") if primary is not None else None,
            "categories": [c.get("term") for c in entry.findall("a:category", arxiv_meta.NS) if c.get("term")],
            "comment": text("arxiv:comment"),
            "journal_ref": text("arxiv:journal_ref"),
            "doi": text("arxiv:doi"),
        }
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pages-per-query", type=int, default=2, help="1,000 candidates per page")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / ".gitignore").write_text("# ~1 GB of downloaded PDFs; regenerate with chatbot/download_top_cited.py\n*\n")

    candidates = ranked_candidates(args.pages_per_query)
    print(f"{len(candidates)} candidates with arXiv IDs", flush=True)

    selected: list[dict] = []
    for start in range(0, len(candidates), 100):
        if len(selected) >= args.count:
            break
        batch = candidates[start:start + 100]
        meta = arxiv_batch([p["arxiv_id"] for p in batch])
        time.sleep(3)
        for paper in batch:
            info = meta.get(paper["arxiv_id"])
            if info and ML_CATEGORIES & set(info["categories"]) and len(selected) < args.count:
                selected.append({**info, "citation_count": paper["citation_count"],
                                 "semantic_scholar_id": paper["semantic_scholar_id"],
                                 "rank": len(selected) + 1})
    print(f"{len(selected)} ML/AI papers selected", flush=True)
    (args.out / "manifest.json").write_text(json.dumps(
        [{k: p[k] for k in ("rank", "arxiv_id", "title", "citation_count", "published", "primary_category")}
         for p in selected], indent=2))

    failures = []
    for paper in selected:
        pdf_path = args.out / f"{paper['arxiv_id']}.pdf"
        (args.out / f"{paper['arxiv_id']}.json").write_text(json.dumps(paper, indent=2, ensure_ascii=False))
        if pdf_path.exists() and pdf_path.read_bytes()[:4] == b"%PDF":
            continue
        try:
            pdf = arxiv_meta.fetch(f"https://export.arxiv.org/pdf/{paper['arxiv_id']}", 100 << 20, timeout=120)
            if not pdf.startswith(b"%PDF"):
                raise ValueError("not a PDF")
            pdf_path.write_bytes(pdf)
            print(f"#{paper['rank']:>3} {paper['arxiv_id']} {paper['citation_count']:>7} cites  "
                  f"{len(pdf) // 1024:>6} KB  {paper['title'][:60]}", flush=True)
        except Exception as exc:
            failures.append(paper["arxiv_id"])
            print(f"#{paper['rank']:>3} {paper['arxiv_id']} FAILED: {exc}", flush=True)
        time.sleep(3)  # arXiv's requested spacing for automated downloads
    print(f"done: {len(selected) - len(failures)} PDFs in {args.out}; failed: {failures or 'none'}")


if __name__ == "__main__":
    main()
