"""Describe Docling-extracted figures with Nova Lite and add them as "figure" chunks.

Run docling_chunks.py --figures first. For each paper this reads
out/figures/<sha256>/figures.json, sends every figure image plus the paper title
and caption to Nova Lite (Bedrock Converse), stores the description back in
figures.json (so reruns are free), and rewrites out/<sha256>.jsonl with one
"figure" chunk per figure appended after the text and table chunks (its "image"
field is the PNG's key in the chunks bucket, shown as a thumbnail in the chat):

    Figure (page 3) from "<paper title>": <caption>
    Description: <what the figure shows: axes, labels, values, trends, components>

    uv run --with boto3 python local_ingest/describe_figures.py [--limit N] [--upload]
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3

OUT = Path(__file__).parent / "out"
MODEL_ID = os.environ.get("FIGURE_MODEL_ID", "amazon.nova-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-west-2")

# Description first (so it is always written), text grouped by panel, no axis
# ticks, capped: transcribing every tick made Nova Lite repeat empty " | "
# separators until the token limit for 73 plots. Words from the PDF's text layer
# (docling_chunks.py "pdf_text") are only a spelling hint: they come without
# layout, so pasting them into the chunk lost which pie a value belonged to.
PROMPT = """This figure is from the paper "{title}" (page {page}).
Caption: {caption}
{hint}
Write two sections for a search index, using only what is visible in the image.

Description: at most 120 words. What kind of figure it is and what it shows. For plots:
which series is highest and which is lowest, where, and roughly by how much, naming each
series by its legend label; say which series a marker such as * or an annotation belongs
to. For diagrams: how the labeled blocks connect, from input to output.

Text in figure: the words and printed values, grouped by panel or chart (for example
"YOLO: Correct 65.5%, Loc 19.0%"): block and layer names, legend entries, axis titles,
labels on arrows, example inputs, values printed on bars or slices. Leave out axis tick
numbers. At most 80 items."""

PDF_HINT = "Words printed in the figure, from the PDF (exact spelling, not in layout order): {pdf_text}\n"

bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def describe(image: bytes, title: str, page: int, caption: str, pdf_text: str = "") -> tuple[str, dict]:
    prompt = PROMPT.format(title=title, page=page, caption=caption or "(none)",
                           hint=PDF_HINT.format(pdf_text=pdf_text) if pdf_text else "")
    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [
            {"image": {"format": "png", "source": {"bytes": image}}},
            {"text": prompt},
        ]}],
        inferenceConfig={"maxTokens": 600, "temperature": 0},
    )
    text = response["output"]["message"]["content"][0]["text"].strip()
    return text, response["usage"]


def figure_chunk(title: str, fig: dict) -> str:
    head = f'Figure (page {fig["page"]}) from "{title}"'
    if fig["caption"]:
        head += f': {fig["caption"]}'
    body = fig["description"]
    if not body.startswith(("Description", "Text in figure")):
        body = f"Description: {body}"
    return f"{head}\n{body}"


def process(jsonl: Path, s3, bucket: str | None, redo: bool = False,
            files: set[str] = frozenset()) -> tuple[int, int, int]:
    doc_id = jsonl.stem
    index_path = OUT / "figures" / doc_id / "figures.json"
    figures = json.loads(index_path.read_text())
    lines = [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]
    lines = [l for l in lines if l.get("kind") != "figure"]  # rerun replaces old figure chunks
    title, source = lines[0]["title"], lines[0]["source"]

    todo = [f for f in figures if "description" not in f or (redo and (not files or f["file"] in files))]

    def run(fig):
        image = (index_path.parent / fig["file"]).read_bytes()
        fig["description"], usage = describe(image, title, fig["page"], fig["caption"],
                                             fig.get("pdf_text", ""))
        return usage

    with ThreadPoolExecutor(4) as pool:
        usages = list(pool.map(run, todo))
    index_path.write_text(json.dumps(figures, indent=2))

    for fig in figures:
        lines.append({"document_id": doc_id, "source": source, "title": title,
                      "chunk_index": len(lines), "page_number": fig["page"],
                      "content": figure_chunk(title, fig), "kind": "figure",
                      "image": f"figures/{doc_id}/{fig['file']}"})
    jsonl.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    if s3:
        # Images first: the JSONL upload triggers the embedder, and the chat shows
        # figure sources as thumbnails from figures/ (which doesn't trigger it).
        for fig in figures:
            s3.upload_file(str(index_path.parent / fig["file"]), bucket, f"figures/{doc_id}/{fig['file']}",
                           ExtraArgs={"ContentType": "image/png"})
        s3.upload_file(str(jsonl), bucket, f"chunks/{doc_id}.jsonl",
                       ExtraArgs={"ContentType": "application/x-ndjson"})
    return (len(figures), sum(u["inputTokens"] for u in usages), sum(u["outputTokens"] for u in usages))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("doc_ids", nargs="*", help="sha256 ids (default: every paper with figures.json)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--redo", action="store_true", help="describe again even if a description exists")
    parser.add_argument("--files", default="", help="with --redo: only these figure files, e.g. p003_f01.png")
    parser.add_argument("--out", type=Path, help="folder written by docling_chunks.py --out (default local_ingest/out)")
    parser.add_argument("--upload", action="store_true",
                        help="upload figure PNGs and the rewritten JSONL to the chunks bucket")
    args = parser.parse_args()
    if args.out:
        global OUT
        OUT = args.out

    s3 = bucket = None
    if args.upload:
        s3 = boto3.client("s3", region_name=REGION)
        account = boto3.client("sts").get_caller_identity()["Account"]
        bucket = os.environ.get("CHUNKS_BUCKET", f"sam-app-chunks-{account}")

    ids = args.doc_ids or sorted(p.parent.name for p in (OUT / "figures").glob("*/figures.json"))
    ids = ids[: args.limit] if args.limit else ids
    total_in = total_out = total_figs = 0
    for doc_id in ids:
        n, tin, tout = process(OUT / f"{doc_id}.jsonl", s3, bucket, args.redo,
                               set(filter(None, args.files.split(","))))
        total_figs, total_in, total_out = total_figs + n, total_in + tin, total_out + tout
        print(f"{doc_id[:12]}: {n} figures, {tin} in / {tout} out tokens", flush=True)
    cost = total_in * 0.06e-6 + total_out * 0.24e-6
    print(f"{len(ids)} papers, {total_figs} figures, {total_in} in / {total_out} out tokens, ${cost:.4f}")


if __name__ == "__main__":
    main()
