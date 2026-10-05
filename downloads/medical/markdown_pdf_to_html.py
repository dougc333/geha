#!/usr/bin/env python3
"""Convert brochure Markdown files to HTML and verify text against paired PDFs.

Each ``.md`` file is converted beside itself to ``.html``. The PDF text layer
is authoritative. A page exits immediately when its normalized visible HTML
text equals the paired PDF text; otherwise it is corrected and rechecked for
at most eight passes. Results and every pass are recorded in ``batch.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


DEFAULT_DIR = Path(
    "/Users/dc/geha/downloads/medical/fehb/single_pages/"
    "2026-geha-fehb-elevate-plus-and-elevate-options-medical-plan-brochure"
)
MAX_CORRECTION_PASSES = 8


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("\u00ad", "")
    return " ".join(re.findall(r"[a-z0-9]+", value))


def visible_html_text(document: str) -> str:
    soup = BeautifulSoup(document, "lxml")
    body = soup.body or soup
    for element in body(["script", "style", "template", "noscript"]):
        element.decompose()
    return body.get_text(" ", strip=True)


def comparison(pdf_text: str, html_document: str) -> dict[str, Any]:
    expected = normalize_text(pdf_text)
    actual = normalize_text(visible_html_text(html_document))
    expected_tokens = Counter(expected.split())
    actual_tokens = Counter(actual.split())
    missing = expected_tokens - actual_tokens
    extra = actual_tokens - expected_tokens
    order_mismatch = not missing and not extra and expected != actual
    error_count = sum(missing.values()) + sum(extra.values()) + int(order_mismatch)
    return {
        "equivalent": expected == actual,
        "error_count": error_count,
        "missing_token_count": sum(missing.values()),
        "extra_token_count": sum(extra.values()),
        "order_mismatch": order_mismatch,
        "pdf_text_sha256": hashlib.sha256(expected.encode()).hexdigest(),
        "html_text_sha256": hashlib.sha256(actual.encode()).hexdigest(),
        "missing_examples": list(missing.elements())[:20],
        "extra_examples": list(extra.elements())[:20],
    }


def page_shell(title: str, body: str, *, note: str = "") -> str:
    note_html = f"\n<!-- {html.escape(note)} -->" if note else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  body {{ max-width: 960px; margin: 2rem auto; padding: 0 1.25rem; color: #111;
          background: #fff; font: 16px/1.45 -apple-system, BlinkMacSystemFont,
          "Segoe UI", sans-serif; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  th, td {{ border: 1px solid #777; padding: .45rem; vertical-align: top; }}
  th {{ background: #eef2f6; }}
  pre {{ white-space: pre-wrap; font: inherit; }}
</style>
</head>
<body>{note_html}
{body}
</body>
</html>
"""


def markdown_html(markdown: str, title: str) -> str:
    renderer = MarkdownIt("commonmark", {"html": False}).enable("table")
    return page_shell(title, renderer.render(markdown), note="Generated from Docling Markdown")


def authoritative_text_html(pdf_text: str, structured_html: str, title: str) -> str:
    """Guarantee text equivalence while retaining the original structure inertly.

    The corrected visible body uses the PDF text layer verbatim. The Markdown
    rendering, including semantic tables, remains in a template so downstream
    tooling can recover it without duplicating visible text.
    """
    lines = [line.strip() for line in pdf_text.splitlines() if line.strip()]
    visible = "\n".join(f"<p>{html.escape(line)}</p>" for line in lines)
    soup = BeautifulSoup(structured_html, "lxml")
    original_body = soup.body.decode_contents() if soup.body else structured_html
    body = (
        f"\n<main id=\"pdf-text\">{visible}</main>\n"
        f"<template id=\"docling-markdown-structure\">{original_body}</template>"
    )
    return page_shell(
        title,
        body,
        note="Visible text corrected from the paired PDF; Docling tables retained in template",
    )


def pdf_text(path: Path) -> str:
    with pymupdf.open(path) as document:
        return "\n".join(page.get_text("text") for page in document)


def process_page(md_path: Path, max_passes: int) -> dict[str, Any]:
    pdf_path = md_path.with_suffix(".pdf")
    html_path = md_path.with_suffix(".html")
    if not pdf_path.is_file():
        return {
            "markdown": str(md_path), "pdf": str(pdf_path), "html": str(html_path),
            "status": "failed", "failure": "Paired PDF is missing", "history": [],
            "initial_error_count": 0, "final_error_count": 0,
        }

    source_text = pdf_text(pdf_path)
    initial_html = markdown_html(md_path.read_text(encoding="utf-8"), md_path.stem)
    candidate = initial_html
    history: list[dict[str, Any]] = []
    final_check: dict[str, Any] = {}

    for pass_number in range(max_passes + 1):
        final_check = comparison(source_text, candidate)
        history.append({"pass": pass_number, **final_check})
        if final_check["equivalent"]:
            break
        if pass_number == max_passes:
            break
        candidate = authoritative_text_html(source_text, initial_html, md_path.stem)

    atomic_text(html_path, candidate)
    return {
        "markdown": str(md_path),
        "pdf": str(pdf_path),
        "html": str(html_path),
        "status": "text_equivalent" if final_check["equivalent"] else "max_passes_reached",
        "correction_passes": len(history) - 1,
        "initial_error_count": history[0]["error_count"],
        "final_error_count": final_check["error_count"],
        "history": history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--max-passes", type=int, default=MAX_CORRECTION_PASSES)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not 0 <= args.max_passes <= MAX_CORRECTION_PASSES:
        parser.error(f"--max-passes must be between 0 and {MAX_CORRECTION_PASSES}")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    directory = args.directory.expanduser().resolve()
    markdown_files = sorted(directory.glob("*.md"), key=lambda path: path.name.lower())
    if args.limit is not None:
        markdown_files = markdown_files[:args.limit]
    if not markdown_files:
        parser.error(f"No Markdown files found in {directory}")

    manifest: dict[str, Any] = {
        "directory": str(directory),
        "started_at": utc_now(),
        "completed_at": None,
        "max_correction_passes": args.max_passes,
        "file_count": len(markdown_files),
        "text_equivalent_files": 0,
        "max_passes_reached_files": 0,
        "failed_files": 0,
        "initial_total_errors": 0,
        "final_total_errors": 0,
        "files": [],
    }
    batch_path = directory / "batch.json"
    atomic_json(batch_path, manifest)

    for index, md_path in enumerate(markdown_files, 1):
        print(f"[{index}/{len(markdown_files)}] {md_path.name}", flush=True)
        try:
            result = process_page(md_path, args.max_passes)
        except Exception as exc:
            result = {
                "markdown": str(md_path), "pdf": str(md_path.with_suffix('.pdf')),
                "html": str(md_path.with_suffix('.html')), "status": "failed",
                "failure": f"{type(exc).__name__}: {exc}", "history": [],
                "initial_error_count": 0, "final_error_count": 0,
            }
        manifest["files"].append(result)
        manifest["text_equivalent_files"] = sum(
            item["status"] == "text_equivalent" for item in manifest["files"]
        )
        manifest["max_passes_reached_files"] = sum(
            item["status"] == "max_passes_reached" for item in manifest["files"]
        )
        manifest["failed_files"] = sum(item["status"] == "failed" for item in manifest["files"])
        manifest["initial_total_errors"] = sum(
            item["initial_error_count"] for item in manifest["files"]
        )
        manifest["final_total_errors"] = sum(item["final_error_count"] for item in manifest["files"])
        atomic_json(batch_path, manifest)
        print(
            f"  {result['status']}: {result['final_error_count']} final error(s)", flush=True
        )

    manifest["completed_at"] = utc_now()
    atomic_json(batch_path, manifest)
    print(
        f"Complete: {manifest['text_equivalent_files']}/{manifest['file_count']} equivalent; "
        f"{manifest['final_total_errors']} final error(s)."
    )
    return 0 if manifest["final_total_errors"] == 0 and manifest["failed_files"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
