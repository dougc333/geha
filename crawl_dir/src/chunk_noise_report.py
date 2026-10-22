"""CLI for chunk length and noise statistics per document and per family."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .pipeline.chunk_noise import NOISE_FLAGS, build_report

CRAWL_DIR = Path(__file__).resolve().parents[1]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summary_markdown(report: dict) -> str:
    columns = ["group", "documents", "pages", "chunks", "chunks_per_page"]
    columns += [f"{flag}_pct" for flag in NOISE_FLAGS]
    lines = [
        "# Chunk noise report",
        "",
        f"Runs: `{report['runs_root']}`" + (f" (batch `{report['batch']}`)" if report["batch"] else " (newest run per document)"),
        "",
        "Flags are text heuristics: `toc` = 3+ dot-leader or page-number lines; "
        "`form` = 2+ blank fields or checkboxes; `tiny` = under 25 words; "
        f"`boilerplate` = half or more of the chunk's lines appear in at least "
        f"{report['boilerplate_min_documents']:g} documents.",
        "",
        "| " + " | ".join(columns) + " |",
        "|" + "---|" * len(columns),
    ]
    for group in [report["corpus"], *report["families"], *report["length_buckets"]]:
        lines.append("| " + " | ".join(str(group[column]) for column in columns) + " |")
    lines += ["", "## Concentration", ""]
    lines += [f"- {key.replace('_', ' ')}: {value}%" for key, value in report["concentration"].items()]
    lines += [
        f"- chunks grow as pages^{report['chunks_vs_pages_exponent']}",
        f"- repeated-line rank-frequency slope: {report['repeated_line_rank_frequency_slope']} (Zipf is about -1)",
        "",
        "## Most repeated lines",
        "",
    ]
    lines += [f"- {item['documents']} documents: `{item['line']}`" for item in report["most_repeated_lines"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=CRAWL_DIR / "runs")
    parser.add_argument("--batch", help="Use only runs with this batch name, e.g. batch-20261009-all")
    parser.add_argument("--output-dir", type=Path, default=CRAWL_DIR / "reports" / "chunk-noise")
    args = parser.parse_args()

    report = build_report(args.runs_root, args.batch)
    if not report["documents"]:
        raise SystemExit(f"No candidate/chunks.jsonl runs found under {args.runs_root}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output_dir / "documents.csv", report["documents"])
    write_csv(args.output_dir / "families.csv", report["families"])
    (args.output_dir / "summary.md").write_text(summary_markdown(report), encoding="utf-8")
    print(args.output_dir)


if __name__ == "__main__":
    main()
