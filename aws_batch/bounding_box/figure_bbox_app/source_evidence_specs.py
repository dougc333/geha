"""Create reviewable figure evidence from the batch extractor's PDF crops.

These files deliberately are not authored chart specs. A reviewer must confirm
the boxes, labels, values, and geometry before a semantic renderer consumes them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pymupdf


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def assemble_source_evidence_specs(
    pdf_path: Path, document_dir: Path, document_id: str, source_relative: str,
) -> dict:
    """Write bbox-compatible annotations and one provisional spec per PDF page."""
    timestamp = datetime.now(timezone.utc).isoformat()
    annotations = {
        "schema_version": 1,
        "document_id": document_id,
        "source_pdf": source_relative,
        "coordinate_system": "normalized_0_1000",
        "annotation_origin": "automatic_candidates_unreviewed",
        "updated_at": timestamp,
        "pages": {},
    }
    status = {"schema_version": 1, "document_id": document_id,
              "running": False, "updated_at": timestamp, "pages": {}}
    with pymupdf.open(pdf_path) as pdf:
        annotations["page_count"] = pdf.page_count
        for index, page in enumerate(pdf):
            page_number = index + 1
            page_key = str(page_number)
            name = f"page-{page_number:03d}"
            evidence_path = document_dir / "pages" / name / "figure-specs.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            boxes = []
            figures = []
            for item in evidence["figures"]:
                x1, y1, x2, y2 = item["box_pdf_points"]
                boxes.append({
                    "id": item["id"], "kind": "figure",
                    "label": item["native_text"].strip()[:160] or item["id"],
                    "x1": round(x1 / page.rect.width * 1000, 3),
                    "y1": round(y1 / page.rect.height * 1000, 3),
                    "x2": round(x2 / page.rect.width * 1000, 3),
                    "y2": round(y2 / page.rect.height * 1000, 3),
                })
                figures.append({
                    "id": item["id"], "label": boxes[-1]["label"],
                    "box_pt": item["box_pdf_points"],
                    "source_crop": f"pages/{name}/{item['crop']}",
                    "native_text": item["native_text"],
                    "percent_tokens": item["percent_tokens"],
                    "candidate_kind": item["kind"],
                    "chart": None,
                    "status": "needs_review",
                })
            if boxes:
                annotations["pages"][page_key] = boxes
            spec = {
                "schema_version": 1, "document_id": document_id,
                "source_pdf": source_relative, "page": page_number,
                "author": "automatic_pdf_crop_evidence", "generated_at": timestamp,
                "status": "needs_review" if figures else "no_candidate_detected",
                "semantic_render_ready": False,
                "figures": figures,
            }
            spec_path = document_dir / "figure-specs" / f"{name}.json"
            _write(spec_path, spec)
            status["pages"][page_key] = {
                "page": page_number, "state": spec["status"],
                "region_count": len(figures), "spec_path": str(spec_path),
                "message": "Review figure boxes and semantics" if figures else "No automatic figure candidate; review page",
            }
    _write(document_dir / "figure-bounding-boxes.json", annotations)
    _write(document_dir / "spec-generation-status.json", status)
    return {"boxed_pages": len(annotations["pages"]),
            "provisional_specs": annotations["page_count"]}
