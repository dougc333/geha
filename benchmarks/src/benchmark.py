"""Page 4 benchmark using only inputs and copied production code in this folder.

Modes:
  html  — PDF raster + figure crop + model HTML/PNG review/correction + table extraction
  spec  — existing authored spec + native PDF verification + deterministic HTML + table extraction
  both  — run each path once, then print their measured totals and table outputs

The model API and installed Python packages are external services/dependencies. No
project file is read from outside this directory after setup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / ".browsers")
PDF = ROOT / "inputs" / "page-004-source.pdf"
SPEC = ROOT / "inputs" / "page-004-spec.json"

import pymupdf
from PIL import Image
from crawl_dir.src.pipeline import scanned_ingestion
from crawl_dir.src.pipeline import figure_segmentation
from crawl_dir.src.pipeline.figure_specs import (
    native_box_evidence,
    render_figure,
    standalone_html,
    verify_figure,
)
from crawl_dir.src.pipeline.tables import extract_logical_tables_from_html


class Timer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.depth = 0

    @contextmanager
    def call(self, name: str):
        index = len(self.calls) + 1
        record: dict[str, Any] = {"call": index, "function": name, "depth": self.depth}
        self.calls.append(record)
        self.depth += 1
        start = time.perf_counter()
        try:
            yield
            record["status"] = "ok"
        except Exception as exc:
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record["milliseconds"] = round((time.perf_counter() - start) * 1000, 2)
            self.depth -= 1

    def wrap(self, obj: Any, name: str, label: str | None = None) -> Callable[[], None]:
        original = getattr(obj, name)
        def measured(*args: Any, **kwargs: Any) -> Any:
            with self.call(label or name):
                return original(*args, **kwargs)
        setattr(obj, name, measured)
        return lambda: setattr(obj, name, original)


def load_spec(timer: Timer) -> tuple[dict[str, Any], dict[str, Any]]:
    with timer.call("read_and_parse_spec_json"):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if spec.get("page") != 4 or len(spec.get("figures", [])) != 1:
        raise ValueError("This benchmark expects the copied page-004 spec with one figure")
    return spec, spec["figures"][0]


def table_from_html(timer: Timer, html_path: Path, output_dir: Path) -> list[dict[str, Any]]:
    with timer.call("extract_logical_tables_from_html"):
        records, _details = extract_logical_tables_from_html(
            [(4, html_path)], output_dir,
            document_id="ey-limra-workforce-benefits-study-final-2025",
            document_version="2025", plan_year=None,
        )
    if not records:
        raise ValueError(f"No semantic HTML table was extracted from {html_path}")
    return records


def prepare_crop(timer: Timer, figure: dict[str, Any], run_dir: Path) -> tuple[Path, dict[str, Any], Path]:
    page_dir = run_dir / "pages" / "page-004"
    segment_dir = page_dir / "segments"
    segment_dir.mkdir(parents=True)
    page_pdf = page_dir / "source.pdf"
    with timer.call("copy_source_pdf_into_run"):
        shutil.copy2(PDF, page_pdf)
    source_png = page_dir / "source.png"
    crop_png = segment_dir / "figure-01-fig1.png"
    with timer.call("render_source_pdf_page_and_crop_figure"):
        with pymupdf.open(page_pdf) as document:
            page = document[0]
            pixmap = page.get_pixmap(dpi=180, alpha=False)
            pixmap.save(source_png)
            sx = pixmap.width / page.rect.width
            sy = pixmap.height / page.rect.height
            x0, y0, x1, y1 = figure["box_pt"]
            box = [round(x0*sx), round(y0*sy), round(x1*sx), round(y1*sy)]
        with Image.open(source_png) as image:
            image.crop(tuple(box)).save(crop_png)
    segmentation = {"regions": [{
        "id": figure["id"], "kind": "chart", "title": figure["title"],
        "image": crop_png.name, "pixel_box": box,
    }]}
    return source_png, segmentation, segment_dir


def benchmark_html(model: str, max_iterations: int, run_dir: Path) -> dict[str, Any]:
    timer = Timer()
    started = time.perf_counter()
    _spec, figure = load_spec(timer)  # box only; chart values are never passed to the model
    source_png, segmentation, segment_dir = prepare_crop(timer, figure, run_dir)
    restores: list[Callable[[], None]] = []
    for name in ("generate_initial_html_with_claude", "_render_html",
                 "review_chart_html_with_claude", "correct_with_claude"):
        restores.append(timer.wrap(scanned_ingestion, name))
    restores.append(timer.wrap(figure_segmentation, "extract_native_figure_evidence"))
    try:
        with timer.call("generate_page_html_with_corrected_figures"):
            figure_segmentation.generate_page_html_with_corrected_figures(
                source_png, segmentation, segment_dir, model,
                max_iterations=max_iterations, assemble_page=False,
            )
    finally:
        for restore in reversed(restores):
            restore()
    batch = json.loads((segment_dir / "batch.json").read_text(encoding="utf-8"))
    final_html = segment_dir / "figure-01" / "final.html"
    tables = table_from_html(timer, final_html, run_dir / "tables")
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return {"mode": "html", "status": batch["status"], "total_ms": elapsed,
            "model": model, "iterations": batch["summary"]["total_iterations"],
            "calls": timer.calls, "table_records": tables,
            "html": str(final_html.relative_to(run_dir)),
            "batch": str((segment_dir / "batch.json").relative_to(run_dir))}


def benchmark_spec(run_dir: Path) -> dict[str, Any]:
    timer = Timer()
    started = time.perf_counter()
    _spec, figure = load_spec(timer)
    with timer.call("native_box_evidence"):
        evidence = native_box_evidence(PDF, figure["box_pt"])
    with timer.call("verify_figure_against_pdf_text"):
        errors, warnings = verify_figure(figure, evidence)
    if errors:
        raise ValueError(f"Existing spec does not verify against this PDF: {errors}")
    with timer.call("render_figure_from_spec"):
        fragment = render_figure(figure)
    with timer.call("standalone_html_from_spec"):
        document = standalone_html(figure["title"], fragment)
    run_dir.mkdir(parents=True, exist_ok=True)
    html_path = run_dir / "figure-from-spec.html"
    with timer.call("write_spec_html"):
        html_path.write_text(document, encoding="utf-8")
    tables = table_from_html(timer, html_path, run_dir / "tables")
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    return {"mode": "spec", "status": "passed", "total_ms": elapsed,
            "model": None, "iterations": 0, "calls": timer.calls,
            "native_evidence_word_count": evidence["word_count"],
            "warnings": warnings, "table_records": tables,
            "html": str(html_path.relative_to(run_dir))}


def print_result(result: dict[str, Any]) -> None:
    print(f"\n{result['mode'].upper()}  status={result['status']}  total={result['total_ms']:,.2f} ms")
    for call in result["calls"]:
        indent = "  " * call["depth"]
        print(f"  {call['call']:02d}  {indent}{call['function']:<44} {call['milliseconds']:>10,.2f} ms  {call['status']}")
    for table in result["table_records"]:
        print(f"  table: {len(table['rows'])} rows × {len(table['headers'])} columns")
        print(f"  headers: {table['headers']}")
        for row in table["rows"]:
            print(f"    {row}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("html", "spec", "both"))
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if not PDF.is_file() or not SPEC.is_file():
        parser.error("Copy inputs/page-004-source.pdf and inputs/page-004-spec.json first")
    if not 1 <= args.max_iterations <= 6:
        parser.error("--max-iterations must be 1..6")
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    run_dir = ROOT / "results" / run_id
    if run_dir.exists():
        parser.error(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    results = []
    comparison = None
    try:
        if args.mode in ("html", "both"):
            result = benchmark_html(args.model, args.max_iterations, run_dir / "html")
            results.append(result)
            print_result(result)
        if args.mode in ("spec", "both"):
            result = benchmark_spec(run_dir / "spec")
            results.append(result)
            print_result(result)
        if len(results) == 2:
            html_ms, spec_ms = results[0]["total_ms"], results[1]["total_ms"]
            print(f"\nTOTAL RATIO: HTML+PNG loop / existing spec = {html_ms/spec_ms:,.1f}×")
            html_table = results[0]["table_records"][0]
            spec_table = results[1]["table_records"][0]
            shared_headers = [header for header in spec_table["headers"] if header in html_table["headers"]]
            shared_rows_equal = (
                len(html_table["rows"]) == len(spec_table["rows"])
                and all(
                    {header: html_row[header] for header in shared_headers}
                    == {header: spec_row[header] for header in shared_headers}
                    for html_row, spec_row in zip(html_table["rows"], spec_table["rows"])
                )
            )
            comparison = {
                "ratio_html_to_spec": round(html_ms / spec_ms, 1),
                "shared_headers": shared_headers,
                "shared_rows_equal": shared_rows_equal,
                "html_only_headers": [header for header in html_table["headers"] if header not in spec_table["headers"]],
                "spec_only_headers": [header for header in spec_table["headers"] if header not in html_table["headers"]],
            }
            print(f"SHARED TABLE FIELDS MATCH: {shared_rows_equal}")
            print(f"HTML-ONLY COLUMNS: {comparison['html_only_headers']}")
            print(f"SPEC-ONLY COLUMNS: {comparison['spec_only_headers']}")
            if results[0]["status"] != "passed":
                print("HTML+PNG review did not pass; this ratio is timing only, not a successful-output comparison.")
        (run_dir / "timings.json").write_text(json.dumps({"inputs": {
            "pdf": str(PDF.relative_to(ROOT)), "spec": str(SPEC.relative_to(ROOT))},
            "results": results, "comparison": comparison}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    finally:
        print(f"\nArtifacts: {run_dir}")


if __name__ == "__main__":
    main()
