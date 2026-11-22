"""Automate page annotation, crop reconstruction, and reviewed semantic specs.

Run from the aws_batch project with its local virtual environment. The browser
agent and correction loop are copied into this project and use no GEHA code
outside aws_batch. Automated review is recorded separately from human approval.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def run_step(args: list[str]) -> None:
    subprocess.run([sys.executable, *args], cwd=PROJECT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-box and reconstruct PDF figure regions")
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="comma-separated 1-based page numbers")
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--max-box-turns", type=int, default=12)
    parser.add_argument("--port", type=int, default=8552)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--limit-regions", type=int, help="bounded smoke tests only")
    args = parser.parse_args()
    pdf = args.pdf.resolve()
    if not pdf.is_file():
        parser.error(f"PDF does not exist: {pdf}")
    pages = sorted({int(value) for value in args.pages.split(",")})
    if not pages or pages[0] < 1:
        parser.error("--pages must contain positive page numbers")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (args.output_root or PROJECT / "runs" / "semantic" / pdf.stem / stamp).resolve()
    root.mkdir(parents=True, exist_ok=False)
    annotations = root / "annotations"
    annotations.mkdir()
    annotation_file = annotations / "figure-bounding-boxes.json"
    run_step(["-m", "bounding_box.figure_bbox_app.browser_bbox_agent", "--pdf", str(pdf),
              "--out-dir", str(annotations), "--pages", ",".join(map(str, pages)),
              "--model", args.model, "--max-turns", str(args.max_box_turns),
              "--port", str(args.port)])
    saved = json.loads(annotation_file.read_text(encoding="utf-8"))
    results = []
    for page in pages:
        boxes = saved.get("pages", {}).get(str(page), [])
        if not any(box.get("kind") != "image" for box in boxes):
            results.append({"page": page, "status": "no-semantic-regions", "box_count": len(boxes)})
            continue
        command = ["-m", "bounding_box.figure_bbox_app.process_annotated_page",
                   "--pdf", str(pdf), "--out-dir", str(annotations),
                   "--output-root", str(root / "reconstruction"),
                   "--page", str(page), "--model", args.model,
                   "--max-iterations", str(args.max_iterations),
                   "--run-id", f"page-{page:03d}"]
        if args.limit_regions:
            command += ["--limit-regions", str(args.limit_regions)]
        run_step(command)
        manifest = json.loads((root / "reconstruction" / f"page-{page:03d}" / "run-manifest.json").read_text())
        results.append({"page": page, "status": manifest["status"], "box_count": len(boxes),
                        "spec": manifest.get("spec"), "review_report": manifest.get("report")})
    summary = {"source_pdf": str(pdf), "pages": results,
               "annotation_file": str(annotation_file), "human_review_status": "pending"}
    (root / "semantic-flow.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(root / "semantic-flow.json")


if __name__ == "__main__":
    main()
