"""Derive a visually corrected immutable run from an existing canonical run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from .pipeline.artifact_io import atomic_json, sha256_file
from .pipeline.claude_client import CLAUDE_MODEL
from .pipeline.figure_segmentation import (
    MAX_FIGURE_ITERATIONS,
    generate_page_html_with_corrected_figures,
    segment_charts_and_figures,
)
from .pipeline.page_content import classify_pdf_pages
from .pipeline.model_client import SUPPORTED_PROVIDERS, use_model_provider
from .pipeline.scanned_ingestion import (
    process_scanned_document,
    review_chart_html_with_claude,
)


RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Required run artifact is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in run artifact: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _base_run_context(base_run: Path) -> dict[str, Any]:
    base_run = base_run.expanduser().resolve()
    if not base_run.is_dir():
        raise FileNotFoundError(f"Base run does not exist: {base_run}")
    if len(base_run.parents) < 4 or base_run.parents[2].name != "runs":
        raise ValueError(
            "Base run must be runs/<family>/<document-id>/<run-id>: "
            f"{base_run}"
        )

    root = base_run.parents[3]
    family = base_run.parents[1].name
    document_id = base_run.parent.name
    manifest_path = base_run / "run-manifest.json"
    manifest = _read_json(manifest_path)
    qc = _read_json(base_run / "qc-report.json")

    if manifest.get("run_id") != base_run.name:
        raise ValueError(
            f"Run ID mismatch: directory is {base_run.name!r}, manifest has "
            f"{manifest.get('run_id')!r}"
        )
    if manifest.get("family") != family:
        raise ValueError(
            f"Family mismatch: directory is {family!r}, manifest has "
            f"{manifest.get('family')!r}"
        )
    if manifest.get("document_id") != document_id:
        raise ValueError(
            f"Document ID mismatch: directory is {document_id!r}, manifest has "
            f"{manifest.get('document_id')!r}"
        )

    source_value = manifest.get("source")
    if not isinstance(source_value, str):
        raise ValueError(f"Missing source path in {manifest_path}")
    source_relative = Path(source_value)
    raw_family = Path("raw") / family
    try:
        document = source_relative.relative_to(raw_family)
    except ValueError as error:
        raise ValueError(
            f"Manifest source must be below {raw_family}: {source_relative}"
        ) from error
    source = (root / source_relative).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Raw source PDF is missing: {source}")
    expected_hash = manifest.get("source_sha256")
    actual_hash = sha256_file(source)
    if expected_hash != actual_hash:
        raise ValueError(
            "Raw source hash no longer matches the base run: "
            f"expected {expected_hash}, got {actual_hash}"
        )

    page_count = qc.get("page_count")
    if not isinstance(page_count, int) or page_count < 1:
        raise ValueError(f"Invalid page_count in {base_run / 'qc-report.json'}")
    missing_pages = [
        page for page in range(1, page_count + 1)
        if not (base_run / "pages" / f"page-{page:03d}" / "source.pdf").is_file()
    ]
    if missing_pages:
        raise FileNotFoundError(
            f"Base run is missing single-page PDFs: {missing_pages}"
        )

    return {
        "base_run": base_run,
        "root": root,
        "family": family,
        "document": str(document),
        "document_id": document_id,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "page_count": page_count,
    }


def _write_derived_page_content(output: Path) -> None:
    """Regenerate page classifications using the derived run's table IDs."""
    table_records = [
        _read_json(path)
        for path in sorted((output / "candidate" / "tables").glob("table-*.json"))
    ]
    report = classify_pdf_pages(output / "input" / "source.pdf", table_records)
    atomic_json(output / "candidate" / "page-content.json", report)
    by_page = {int(item["page"]): item for item in report["pages"]}
    for page, classification in by_page.items():
        manifest_path = output / "pages" / f"page-{page:03d}" / "page-manifest.json"
        manifest = _read_json(manifest_path)
        manifest.update({
            "page_type": classification["page_type"],
            "content_types": classification["content_types"],
            "table_detected": classification["table_detected"],
            "figure_detected": classification["figure_detected"],
            "scanned_page": classification["scanned_page"],
            "visual_review_recommended": classification[
                "visual_review_recommended"
            ],
            "detection_signals": classification["signals"],
        })
        atomic_json(manifest_path, manifest)


def _record_parent_metadata(
    base_run: Path,
    output: Path,
    visual_pages: set[int],
) -> None:
    """Record page-level derivation without copying stale extraction fields."""
    output_pages = output / "pages"
    for derived_path in sorted(output_pages.glob("page-*/page-manifest.json")):
        derived = _read_json(derived_path)
        page = int(derived["page"])
        derived["parent_run_id"] = base_run.name
        derived["visual_correction_applied"] = page in visual_pages
        atomic_json(derived_path, derived)


def derive_visual_run(
    *,
    base_run: Path,
    pages: list[int],
    output_run: str,
    provider: str = "anthropic",
    model: str | None = None,
    base_url: str | None = None,
    api_key_env: str | None = None,
    max_corrections: int = 6,
    max_figure_iterations: int = 6,
    layout_hint: str = "",
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    """Create a new run with selected pages reconstructed and visually reviewed."""
    if not RUN_NAME.fullmatch(output_run):
        raise ValueError(
            "--output-run must be a simple run name containing letters, numbers, "
            "dots, underscores, or hyphens"
        )
    if model is None:
        if provider != "anthropic":
            raise ValueError("--model is required when --provider is not anthropic")
        model = CLAUDE_MODEL
    if not 1 <= max_figure_iterations <= MAX_FIGURE_ITERATIONS:
        raise ValueError(
            "--max-figure-iterations must be between 1 and "
            f"{MAX_FIGURE_ITERATIONS}"
        )
    context = _base_run_context(base_run)
    selected = sorted(set(pages))
    if not selected:
        raise ValueError("At least one --page is required")
    invalid = [
        page for page in selected
        if page < 1 or page > int(context["page_count"])
    ]
    if invalid:
        raise ValueError(
            f"Pages outside 1..{context['page_count']}: {invalid}"
        )
    expected_output = (
        context["root"] / "runs" / context["family"] /
        context["document_id"] / output_run
    )
    if expected_output.exists():
        raise FileExistsError(expected_output)

    emit = event_sink or (lambda _event: None)

    def generate_visual_page(
        source_png: Path,
        segmentation: dict[str, Any],
        segment_dir: Path,
        selected_model: str,
    ) -> str:
        return generate_page_html_with_corrected_figures(
            source_png,
            segmentation,
            segment_dir,
            selected_model,
            max_iterations=max_figure_iterations,
            event_sink=emit,
        )

    emit({
        "type": "visual_derivation_started",
        "base_run": str(context["base_run"]),
        "output_run": output_run,
        "pages": selected,
        "provider": provider,
        "model": model,
    })
    with use_model_provider(
        provider,
        base_url=base_url,
        api_key_env=api_key_env,
    ) as provider_config:
        output = process_scanned_document(
            root=context["root"],
            family=context["family"],
            document=context["document"],
            document_version=str(context["manifest"]["document_version"]),
            plan_year=context["manifest"].get("plan_year"),
            model=model,
            max_corrections=max_corrections,
            requested_run_id=output_run,
            reviewer=review_chart_html_with_claude,
            page_segmenter=segment_charts_and_figures,
            segmented_generator=generate_visual_page,
            segmentation_layout_hint=layout_hint,
            additional_visual_pages=selected,
            event_sink=emit,
        )
    output = output.resolve()
    if output != expected_output.resolve():
        raise RuntimeError(
            f"Visual pipeline wrote an unexpected run: {output}; expected {expected_output}"
        )

    _write_derived_page_content(output)
    _record_parent_metadata(context["base_run"], output, set(selected))
    derived_manifest_path = output / "run-manifest.json"
    derived_manifest = _read_json(derived_manifest_path)
    derived_manifest.update({
        "pipeline": "derived-visual-correction",
        "parent_run": str(context["base_run"].relative_to(context["root"])),
        "parent_run_id": context["manifest"]["run_id"],
        "parent_manifest_sha256": sha256_file(context["manifest_path"]),
        "page_content": "candidate/page-content.json",
        "visual_reconstruction_pages": selected,
        "derivation": {
            "method": "chart_figure_crop_semantic_html_correction",
            "provider": provider,
            "model": model,
            **({"base_url": provider_config.base_url}
               if provider_config.base_url else {}),
            **({"api_key_env": provider_config.api_key_env}
               if provider_config.api_key_env else {}),
            "max_page_corrections": max_corrections,
            "max_figure_iterations": max_figure_iterations,
        },
    })
    atomic_json(derived_manifest_path, derived_manifest)
    emit({
        "type": "visual_derivation_complete",
        "base_run": str(context["base_run"]),
        "run": str(output),
        "pages": selected,
    })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run", type=Path, required=True)
    parser.add_argument(
        "--page",
        action="append",
        type=int,
        required=True,
        help="One-based page to reconstruct; repeat for multiple pages.",
    )
    parser.add_argument("--output-run", required=True)
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default="anthropic")
    parser.add_argument(
        "--model",
        help=f"Provider model ID; defaults to {CLAUDE_MODEL!r} for Anthropic.",
    )
    parser.add_argument(
        "--base-url",
        help="OpenAI-compatible API base URL, including /v1 when required.",
    )
    parser.add_argument(
        "--api-key-env",
        help="Environment variable containing the provider API key.",
    )
    parser.add_argument("--max-corrections", type=int, default=6)
    parser.add_argument("--max-figure-iterations", type=int, default=6)
    parser.add_argument("--layout-hint", default="")
    args = parser.parse_args()

    output = derive_visual_run(
        base_run=args.base_run,
        pages=args.page,
        output_run=args.output_run,
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
        max_corrections=args.max_corrections,
        max_figure_iterations=args.max_figure_iterations,
        layout_hint=args.layout_hint,
        event_sink=lambda event: print(json.dumps(event), flush=True),
    )
    print(output)


if __name__ == "__main__":
    main()
