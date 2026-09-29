#!/usr/bin/env python3
"""Table-aware chunking with Docling, run on a laptop, uploaded to the pipeline.

    /Users/dc/geha/.venv/bin/python local_ingest/docling_chunks.py PDF_FOLDER \
        [--ids 1512.03385,1706.03762] [--limit 20] [--max-pages 40] [--upload]

For each PDF (with its <id>.json metadata sidecar next to it) this writes
local_ingest/out/<sha256>.jsonl in the same format the chunker Lambda produces,
so the embedder handles it unchanged:

- text chunks: Docling's text blocks per page (headers/footers dropped), joined
  and split like the chunker (350 words, 50 overlap);
- table chunks: one per table, "Table N: caption" plus the table as compact
  Markdown, with "kind": "table". Tables longer than ~4,000 characters are split
  by rows, repeating the header.

document_id is the PDF's SHA-256, as in the chunker, so --upload (to
s3://<chunks bucket>/chunks/) replaces that paper's flat chunks in Neon. The
PDF itself is not uploaded, which would re-trigger the flat chunker.
With --figures, each figure (picture or chart) is also saved as a PNG with its
page and caption in local_ingest/out/figures/<sha256>/figures.json, for
describe_figures.py to turn into "figure" chunks.
Docling is installed in /Users/dc/geha/.venv (not the Lambda).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "query"))
from rag_core import chunk_text  # noqa: E402

# Only running headers/footers are noise. Captions (figures too) and footnotes stay
# in the text: dropping them hid answers such as "Figure 7: CIFAR10 samples…".
SKIP_LABELS = {"page_header", "page_footer"}
MAX_TABLE_CHARS = 4000


def compact_markdown(markdown: str) -> str:
    """Docling pads cells to align columns; the spaces only cost tokens."""
    lines = []
    for line in markdown.splitlines():
        line = re.sub(r" {2,}", " ", line.strip())
        line = re.sub(r"\|-{2,}", "|---", line)
        lines.append(line)
    return "\n".join(lines)


def table_chunks(caption: str, markdown: str) -> list[str]:
    # A single row can exceed the limit (T5 has one ~14k-character row); cut such
    # rows into pieces first so no chunk is too long to embed.
    lines = []
    for line in markdown.splitlines():
        lines += [line[i:i + MAX_TABLE_CHARS] for i in range(0, len(line), MAX_TABLE_CHARS)] or [line]
    markdown = "\n".join(lines)
    header, rows = lines[:2], lines[2:]
    prefix = (caption + "\n\n") if caption else ""
    if len(markdown) <= MAX_TABLE_CHARS or len(lines) < 3:
        return [prefix + markdown]
    parts, current = [], []
    for row in rows:
        if current and len("\n".join(header + current + [row])) > MAX_TABLE_CHARS:
            parts.append(current)
            current = []
        current.append(row)
    if current:
        parts.append(current)
    return [f"{prefix}(part {i} of {len(parts)})\n" + "\n".join(header + part)
            for i, part in enumerate(parts, 1)]


MIN_FIGURE_PX = 150  # uncaptioned images below 150x150 px of area (at images_scale 2) are logos/icons


def keep_figure(width: int, height: int, caption: str) -> bool:
    """Captioned pictures are real figures whatever their shape: wide strips such
    as YOLO's Figure 1 (475x98) or Atari's screenshots (794x103) were dropped by an
    earlier "shorter side >= 150 px" rule. Uncaptioned ones must be large enough."""
    return bool(caption) or width * height >= MIN_FIGURE_PX * MIN_FIGURE_PX


def carry_descriptions(old: list[dict], new: list[dict]) -> int:
    """Copy describe_figures.py's descriptions from the previous figures.json to the
    same figures in a new run. Matched on page, caption and size, not the file name:
    names are numbered in page order, so keeping one more figure renames the rest."""
    def key(f: dict) -> tuple:
        return f["page"], f["caption"], f["width"], f["height"]
    described = {key(f): f["description"] for f in old if "description" in f}
    carried = 0
    for f in new:
        if key(f) in described:
            f["description"] = described[key(f)]
            carried += 1
    return carried


def convert(pdf: Path, converter, figure_dir: Path | None = None
            ) -> tuple[list[tuple[int, str, str]], list[dict], float]:
    """(page, kind, text) chunks for one PDF in reading order, plus its figures
    (saved as PNGs in figure_dir when given)."""
    started = time.perf_counter()
    doc = converter.convert(str(pdf)).document
    pages: dict[int, list[str]] = {}
    tables: list[tuple[int, str]] = []
    figures: list[dict] = []
    for item, _level in doc.iterate_items():
        label = str(getattr(item, "label", "")).split(".")[-1].lower()
        page = item.prov[0].page_no if getattr(item, "prov", None) else 0
        if label in ("picture", "chart") and figure_dir is not None:
            image = item.get_image(doc)
            caption = " ".join(item.caption_text(doc).split())
            if image is not None and keep_figure(*image.size, caption):
                name = f"p{page:03d}_f{len(figures) + 1:02d}.png"
                image.save(figure_dir / name)
                figures.append({"file": name, "page": page, "kind": label, "caption": caption,
                                "width": image.size[0], "height": image.size[1]})
        elif label == "table":
            markdown = compact_markdown(item.export_to_markdown(doc=doc))
            caption = " ".join(item.caption_text(doc).split())
            if caption and markdown.startswith(caption):  # Docling puts the caption first
                markdown = markdown[len(caption):].lstrip()
            for text in table_chunks(caption, markdown):
                tables.append((page, text))
        elif label not in SKIP_LABELS and getattr(item, "text", ""):
            pages.setdefault(page, []).append(item.text)
    chunks = []
    for page in sorted(set(pages) | {p for p, _ in tables}):
        text = " ".join(" ".join(pages.get(page, [])).split())
        chunks += [(page, "text", c) for c in chunk_text(text)] if text else []
        chunks += [(page, "table", t) for p, t in tables if p == page]
    return chunks, figures, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--ids", default="", help="comma-separated arXiv IDs (default: all with sidecars)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-pages", type=int, default=0, help="skip longer PDFs (0 = no limit)")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--figures", action="store_true",
                        help="also save figure images to out/figures/<doc_id>/ for describe_figures.py")
    parser.add_argument("--region", default="us-west-2")
    args = parser.parse_args()

    import pymupdf
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(do_ocr=False, do_table_structure=True,  # born-digital PDFs
                                 generate_picture_images=args.figures, images_scale=2.0)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

    ids = [i.strip() for i in args.ids.split(",") if i.strip()] or sorted(
        p.stem for p in args.folder.glob("*.pdf") if p.with_suffix(".json").exists())
    out_dir = HERE / "out"
    out_dir.mkdir(exist_ok=True)
    s3 = bucket = None
    if args.upload:
        import boto3
        s3 = boto3.client("s3", region_name=args.region)
        outputs = boto3.client("cloudformation", region_name=args.region).describe_stacks(
            StackName="sam-app")["Stacks"][0]["Outputs"]
        bucket = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "ChunkBucketName")

    done = 0
    for arxiv_id in ids:
        if args.limit and done >= args.limit:
            break
        pdf = args.folder / f"{arxiv_id}.pdf"
        with pymupdf.open(pdf) as document:
            if args.max_pages and document.page_count > args.max_pages:
                print(f"skip {arxiv_id} ({document.page_count} pages)")
                continue
        metadata = json.loads(pdf.with_suffix(".json").read_text())
        doc_id = hashlib.sha256(pdf.read_bytes()).hexdigest()
        figure_dir = None
        if args.figures:
            figure_dir = out_dir / "figures" / doc_id
            figure_dir.mkdir(parents=True, exist_ok=True)
        chunks, figures, seconds = convert(pdf, converter, figure_dir)
        if figure_dir is not None:
            # Keep descriptions already made by describe_figures.py for the same figures.
            figure_index = figure_dir / "figures.json"
            if figure_index.exists():
                carry_descriptions(json.loads(figure_index.read_text()), figures)
            figure_index.write_text(json.dumps(figures, indent=2))
        lines = []
        for index, (page, kind, text) in enumerate(chunks):
            line = {"document_id": doc_id, "source": f"docling:{pdf.name}", "title": metadata["title"],
                    "chunk_index": index, "page_number": page, "content": text.replace("\x00", ""),
                    "kind": kind}
            if index == 0:
                line["metadata"] = {k: v for k, v in metadata.items()
                                    if k not in {"citation_count", "rank", "semantic_scholar_id"}}
            lines.append(json.dumps(line))
        path = out_dir / f"{doc_id}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        n_tables = sum(1 for _, kind, _ in chunks if kind == "table")
        print(f"{arxiv_id}: {len(chunks)} chunks ({n_tables} table, {len(figures)} figures) "
              f"in {seconds:.0f}s  {metadata['title'][:50]}", flush=True)
        if s3:
            s3.upload_file(str(path), bucket, f"chunks/{doc_id}.jsonl",
                           ExtraArgs={"ContentType": "application/x-ndjson"})
        done += 1


if __name__ == "__main__":
    main()
