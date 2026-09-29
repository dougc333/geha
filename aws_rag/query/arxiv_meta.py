"""Fetch paper metadata from the arXiv API (export.arxiv.org, Atom feed).

Used by POST /api/arxiv and scripts/backfill_arxiv_metadata.py. The result is
stored in a sidecar JSON next to the PDF in S3 (<key>.json), carried into the
chunk file by the chunker, and written to rag_documents by the embedder.
"""

from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "aws-rag-chatbot/1.0"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# New-style arXiv IDs (2305.14314, optionally v2), bare or inside a URL/filename.
ARXIV_ID = re.compile(r"(?<![\d.])(\d{4}\.\d{4,5})(v\d+)?(?!\d)")


def find_arxiv_id(text: str) -> str | None:
    """The arXiv ID (with version, if present) in an ID, URL or file name."""
    match = ARXIV_ID.search(text or "")
    return match.group(1) + (match.group(2) or "") if match else None


def fetch(url: str, limit: int, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"response larger than {limit} bytes")
    return data


def _clean(text: str | None) -> str | None:
    text = " ".join((text or "").split())
    return text or None


def metadata(arxiv_id: str) -> dict | None:
    """Metadata for one paper, or None if arXiv has no such paper."""
    feed = ET.fromstring(fetch(
        f"https://export.arxiv.org/api/query?id_list={arxiv_id}&max_results=1", 1 << 20
    ))
    entry = feed.find("a:entry", NS)
    title = _clean(entry.findtext("a:title", "", NS)) if entry is not None else None
    if entry is None or not title or title == "Error":
        return None
    primary = entry.find("arxiv:primary_category", NS)
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": [
            name for author in entry.findall("a:author", NS)
            if (name := _clean(author.findtext("a:name", "", NS)))
        ],
        "published": (entry.findtext("a:published", "", NS) or "")[:10] or None,
        "updated": (entry.findtext("a:updated", "", NS) or "")[:10] or None,
        "abstract": _clean(entry.findtext("a:summary", "", NS)),
        "primary_category": primary.get("term") if primary is not None else None,
        "categories": [c.get("term") for c in entry.findall("a:category", NS) if c.get("term")],
        "comment": _clean(entry.findtext("arxiv:comment", "", NS)),
        "journal_ref": _clean(entry.findtext("arxiv:journal_ref", "", NS)),
        "doi": _clean(entry.findtext("arxiv:doi", "", NS)),
    }
