"""Alt-2 template adapter for the existing React ingestion worker.

OCR remains source-driven. The reviewed geometry selects crops; no gold answer is
loaded during a run. Gold comparisons belong in offline evaluation.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from crawl_dir.src.pipeline.artifact_io import atomic_json
from document_ingestion_workflow import bill_of_lading_workflow as shared

LAYOUT = Path(__file__).with_name("layout.json")


def segment(source_png: Path, output_dir: Path, model: str, layout_hint: str = "") -> dict[str, Any]:
    # The shared segmenter scales the named cells to the actual rendered page.
    return shared.segment_bill_of_lading_with_schema(source_png, output_dir, model, layout_hint)


def _page_html(segmentation: dict[str, Any], cells_by_block: dict[int, dict[str, str]]) -> str:
    """Render source-positioned form fields with semantic one-row cargo tables."""
    canvas = segmentation["schema"]["source_canvas"]
    blocks = segmentation["schema"]["blocks"]

    def esc(value: str) -> str:
        return html.escape(value)

    def box_style(box: dict[str, int]) -> str:
        return (f'left:{box["x"]}px;top:{box["y"]}px;'
                f'width:{box["width"]}px;height:{box["height"]}px')

    def cell_html(cell: dict[str, Any], number: int) -> str:
        cell_id = cell["id"]
        value = cells_by_block[number].get(cell_id, "")
        if cell_id == "signature":
            match = re.search(r"SIGNED on behalf of the\s+(.+?)\s*Agent Signature", value, re.I | re.S)
            if match:
                content = ('<div>SIGNED on behalf of the <span class="signature-name">'
                           + esc(match.group(1).strip()) + '</span></div>'
                           '<div class="signature-redaction"></div>'
                           '<div class="signature-caption">Agent Signature</div>')
            else:
                content = f'<pre>{esc(value)}</pre>'
        else:
            content = f'<pre>{esc(value)}</pre>'
        return (f'<div class="cell" data-cell="{esc(cell_id)}" '
                f'style="{box_style(cell["box"])}">{content}</div>')

    sections: list[str] = []
    for block in blocks:
        number = block["block"]
        if number in (5, 6, 7):
            continue
        sections.append(
            f'<section class="block block-{number}" style="{box_style(block["box"])}">'
            + ''.join(cell_html(cell, number) for cell in block["cells"])
            + '</section>'
        )

    # The source has one cargo data row. The two repeated amounts are totals,
    # placed over the lower parts of the weight/measurement columns.
    header = cells_by_block[5]
    cargo = cells_by_block[6]
    cargo_box = blocks[4]["box"]
    cargo_height = cargo_box["height"] + blocks[5]["box"]["height"]
    cargo_widths = [c["box"]["width"] for c in blocks[4]["cells"]]
    colgroup = ''.join(f'<col style="width:{width}px">' for width in cargo_widths)
    headings = ''.join(f'<th scope="col">{esc(header.get(f"cargo_header_{i}", ""))}</th>'
                       for i in range(1, 5))
    values = ''.join(f'<td data-cell="cargo_cell_{i}">{esc(cargo.get(f"cargo_cell_{i}", ""))}</td>'
                     for i in range(1, 5))
    weight_box = blocks[5]["cells"][4]["box"]
    measurement_box = blocks[5]["cells"][5]["box"]
    total_top = cargo_box["height"] + weight_box["y"]
    sections.append(
        f'<section class="cargo-section" style="left:{cargo_box["x"]}px;'
        f'top:{cargo_box["y"]}px;width:{cargo_box["width"]}px;height:{cargo_height}px">'
        f'<table class="cargo-table"><colgroup>{colgroup}</colgroup>'
        f'<thead><tr>{headings}</tr></thead><tbody><tr class="cargo-row">{values}</tr></tbody></table>'
        f'<div class="cargo-total weight-total" style="left:{weight_box["x"]}px;'
        f'top:{total_top}px;width:{weight_box["width"]}px;height:{weight_box["height"]}px">'
        f'{esc(cargo.get("weight_total", ""))}</div>'
        f'<div class="cargo-total measurement-total" style="left:{measurement_box["x"]}px;'
        f'top:{total_top}px;width:{measurement_box["width"]}px;height:{measurement_box["height"]}px">'
        f'{esc(cargo.get("measurement_total", ""))}</div>'
        '</section>'
    )

    charges = cells_by_block[7]
    charge_box = blocks[6]["box"]
    charge_cells = {cell["id"]: cell for cell in blocks[6]["cells"]}
    charge_widths = [charge_cells[f"charge_header_{i}"]["box"]["width"] for i in range(1, 6)]
    charge_colgroup = ''.join(f'<col style="width:{width}px">' for width in charge_widths)
    charge_headings = ''.join(f'<th scope="col">{esc(charges.get(f"charge_header_{i}", ""))}</th>'
                              for i in range(1, 6))
    caption_box = charge_cells["charges_caption"]["box"]
    body_box = charge_cells["charges_body"]["box"]
    legal_box = charge_cells["legal_terms"]["box"]
    sections.append(
        f'<section class="block block-7" style="{box_style(charge_box)}">'
        f'<div class="charge-caption" style="{box_style(caption_box)}">'
        f'{esc(charges.get("charges_caption", ""))}</div>'
        f'<table class="charges-table" style="left:0;top:{caption_box["height"]}px;'
        f'width:{body_box["width"]}px;height:{charge_box["height"]-caption_box["height"]}px">'
        f'<colgroup>{charge_colgroup}</colgroup><thead><tr>{charge_headings}</tr></thead><tbody></tbody></table>'
        f'<div class="charge-body-outline" style="left:{body_box["x"]}px;top:{body_box["y"]}px;'
        f'width:{body_box["width"]}px;height:{body_box["height"]}px" aria-hidden="true"></div>'
        f'<div class="cell legal-terms" data-cell="legal_terms" style="{box_style(legal_box)}">'
        f'<pre>{esc(charges.get("legal_terms", ""))}</pre></div>'
        '</section>'
    )

    shipper = cells_by_block[2].get("shipper", "")
    shipper_lines = [line.strip() for line in shipper.splitlines() if line.strip()]
    name = shipper_lines[1] if len(shipper_lines) > 1 else ""
    phone = _match(r"Tel\s*:?\s*(\+?[\d ]+)", shipper) or ""
    email = _match(r"([\w.+-]+@[\w.-]+\.[A-Z]{2,})", shipper) or ""
    footer = ' • '.join(part for part in (name, phone, email) if part)
    if footer:
        sections.append(f'<footer class="page-footer">{esc(footer)}</footer>')

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>Bill of lading alt 2</title><style>'
        '*{box-sizing:border-box}html,body{margin:0;background:#fff}'
        f'.page{{position:relative;width:{canvas["width"]}px;height:{canvas["height"]}px;'
        'font-family:Arial,sans-serif;color:#111}'
        '.block,.cargo-section{position:absolute}'
        '.cell{position:absolute;border:1px solid #222;padding:8px;overflow:hidden}'
        '.cell pre{margin:0;white-space:pre-wrap;font:20px/1.2 Arial,sans-serif}'
        '.block-1 .cell[data-cell="carrier_header"]{border:0;padding:28px 16px}'
        '.block-1 .cell[data-cell="carrier_header"] pre{font-size:24px;line-height:1.4}'
        '.block-1 .cell[data-cell="carrier_header"] pre::first-line{font-size:44px;font-weight:700}'
        '.block-1 .cell[data-cell="bill_of_lading_number"] pre{font-size:24px;line-height:1.4}'
        '.block-1 .cell[data-cell="bill_of_lading_number"] pre::first-line{font-size:40px;font-weight:700}'
        '.block-2 .cell pre::first-line,.block-3 .cell pre::first-line{font-weight:600}'
        '.block-4 .cell{display:grid;place-items:center}'
        '.block-4 .cell pre{font-size:20px;font-weight:700;letter-spacing:1px;text-align:center}'
        '.cargo-table,.charges-table{border-collapse:collapse;table-layout:fixed}'
        '.cargo-table{width:100%;height:100%;font-size:21px}'
        '.cargo-table th,.cargo-table td,.charges-table th{border:1px solid #222;'
        'padding:8px;vertical-align:top;white-space:pre-wrap;text-align:left}'
        f'.cargo-table thead{{height:{cargo_box["height"]}px}}'
        '.cargo-table th{text-align:center;font-weight:700}'
        '.cargo-table td{font-family:Courier New,monospace;font-size:19px}'
        '.cargo-total{position:absolute;border:1px solid #222;border-top:2px solid #111;'
        'background:#fff;padding:8px;font:700 20px/1.2 Courier New,monospace;white-space:pre-wrap}'
        '.charges-table{position:absolute;border:1px solid #222}'
        '.charges-table thead{height:52px}.charges-table th{text-align:center;font-weight:700}'
        '.charge-body-outline{position:absolute;border-left:2px solid #222;'
        'border-right:2px solid #222;border-bottom:2px solid #222;pointer-events:none}'
        '.charge-caption{position:absolute;border:1px solid #222;padding:8px;font-size:18px}'
        '.legal-terms pre{font-size:13px;line-height:1.15}'
        '.block-8 .cell pre::first-line{font-weight:600}'
        '.cell[data-cell="signature"]{position:absolute}'
        '.signature-name{display:inline-block;background:#241e49;color:#fff;padding:0 4px}'
        '.signature-redaction{background:#241e49;width:75%;height:20px;margin-top:14px}'
        '.signature-caption{font:44px/1.1 Arial,sans-serif;text-align:right;margin-top:32px}'
        '.page-footer{position:absolute;left:68px;right:68px;bottom:38px;'
        'border-top:1px solid #ddd;padding-top:24px;color:#666;text-align:center;font-size:26px}'
        '</style></head><body><main class="page">' + ''.join(sections) + '</main></body></html>'
    )


def generate(source_png: Path, segmentation: dict[str, Any], segment_dir: Path,
             model: str, event_sink: Any | None = None) -> str:
    del source_png, event_sink
    extracted: dict[int, dict[str, str]] = {}
    records = []
    for block in segmentation["regions"]:
        number = int(block["reading_order"])
        cells = shared._extract_block_cells(block, segment_dir, model)
        extracted[number] = cells
        records.append({"block": number, "section": block["label"], "cells": cells,
                        "source_region": block["image"]})
    atomic_json(segment_dir / "structured-ocr.json", {
        "schema_version": 1, "template_id": "hemisphere_bill_of_lading_alt_2",
        "workflow_program": str(Path(__file__)), "blocks": records,
    })
    return _page_html(segmentation, extracted)


def correct(source_png: Path, html_png: Path, candidate: str,
            errors: list[dict[str, Any]], model: str) -> str:
    del html_png
    segment_dir = source_png.parent / "segments"
    segmentation = json.loads((segment_dir / "regions.json").read_text())
    record_path = segment_dir / "structured-ocr.json"
    record = json.loads(record_path.read_text())
    extracted = {int(block["block"]): dict(block["cells"]) for block in record["blocks"]}
    failed = shared._failed_cells(errors, extracted)
    if not failed:
        return candidate
    regions = {int(region["reading_order"]): region for region in segmentation["regions"]}
    for number, cell_ids in failed.items():
        extracted[number].update(shared._extract_block_cells(
            regions[number], segment_dir, model, cell_ids=cell_ids, feedback=errors))
    revision = int(record.get("correction_revision", 0)) + 1
    record.update({
        "correction_revision": revision,
        "corrected_cells": {str(number): sorted(ids) for number, ids in failed.items()},
        "blocks": [{**block, "cells": extracted[int(block["block"])]} for block in record["blocks"]],
    })
    atomic_json(segment_dir / f"structured-ocr-correction-{revision:02d}.json", record)
    atomic_json(record_path, record)
    return _page_html(segmentation, extracted)


def _match(pattern: str, text: str, group: int = 1) -> str | None:
    match = re.search(pattern, text, re.I | re.M)
    return re.sub(r"\s+", " ", match.group(group)).strip() if match else None


def _region_value(text: str) -> str | None:
    """Read value lines after a printed label and optional parenthetical note."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    body = lines[1:]
    if body and body[0].endswith(")") and re.fullmatch(r"[\d.]+\)", body[0]):
        body = body[1:]
    return " ".join(body) or None


def _party_values(text: str, label: str) -> dict[str, str | None]:
    """Read one printed party box without filling absent values from another box."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = lines[1:]
    if label == "notify_parties" and body and body[0].lower().startswith("clause "):
        body = body[1:]
    name = body[0] if body else None
    details = [line for line in body[1:] if not re.match(r"Tel\s*:", line, re.I)
               and "@" not in line]
    return {
        "name": name,
        "address": " ".join(details) or None,
        "phone": _match(r"Tel\s*:?\s*(\+?[\d ]+)", text),
        "email": _match(r"([\w.+-]+@[\w.-]+\.[A-Z]{2,})", text),
    }


def parse_cells(cells: dict[str, str]) -> dict[str, Any]:
    """Parse source OCR cells; absent values stay null and retain source evidence."""
    discharge = cells.get("discharge_agent", "")
    cargo1, cargo2 = cells.get("cargo_cell_1", ""), cells.get("cargo_cell_2", "")
    weight, measure = cells.get("cargo_cell_3", ""), cells.get("cargo_cell_4", "")
    agent = re.split(r"PORT OF DISCHARGE AGENT\s*:?", discharge, maxsplit=1, flags=re.I)
    agent_lines = [line.strip() for line in (agent[-1] if len(agent) > 1 else "").splitlines() if line.strip()]
    fields = {
        "bl_number": _match(r"\b(BL\d{6,})\b", cells.get("bill_of_lading_number", "")),
        "scac": _match(r"SCAC\s*Code\s*:?\s*([A-Z]{4})", cells.get("carrier_header", "")),
        "imo_number": _match(r"(?:Lloyds/)?IMO\s*Number\s*:?\s*(\d{7})", discharge),
        "port_of_discharge_agent_name": agent_lines[0] if agent_lines else None,
        "port_of_discharge_agent_address": agent_lines[1] if len(agent_lines) > 1 else None,
        "port_of_discharge_agent_phone": _match(r"Tel\s*:?\s*(\+?[\d ()-]+)", discharge),
        "port_of_discharge_agent_email": _match(r"([\w.+-]+@[\w.-]+\.[A-Z]{2,})", discharge),
        "booking_number": _match(r"\b(BKG\d+)\b", cells.get("booking_and_shipper_reference", "")),
        "shipper_ref": _match(r"\b(EXP-\d+)\b", cells.get("booking_and_shipper_reference", "")),
        "place_of_receipt": _region_value(cells.get("place_of_receipt", "")),
        "place_of_delivery": _region_value(cells.get("place_of_delivery", "")),
        "port_of_loading": _region_value(cells.get("port_of_loading", "")),
        "port_of_discharge": _region_value(cells.get("port_of_discharge", "")),
        "freight_terms": _match(r"FREIGHT\s+(PREPAID|COLLECT)", cargo2),
        "total_packages": int(v) if (v := _match(r"Total Items\s*:?\s*(\d+)", cargo2)) else None,
    }
    bill_header = cells.get("bill_of_lading_number", "")
    fields.update({
        "document_id": fields["bl_number"],
        "bill_of_lading_type": _match(r"(NON-NEGOTIABLE COPY)", bill_header),
        "number_of_rider_pages": int(v) if (v := _match(r"(?:RIDER PAGES)[^\n]*\n(\d+)", bill_header)) else None,
        "carrier_name": (cells.get("carrier_header", "").splitlines() or [None])[0],
        "carrier_agents_endorsements": _match(r"(SHIPPER'S LOAD, COUNT AND SEALED)",
                                                cells.get("carrier_agent_endorsements", "")),
        "type_of_movement": _match(r"\b(FCL/FCL|LCL/LCL|FCL/LCL|LCL/FCL)\b",
                                   cells.get("carrier_agent_endorsements", "")),
        "carriers_receipt": _match(r"(\d+\s+cntr)", cells.get("carrier_receipt", "")),
        "laden_on_board_date": _match(r"\b(\d{4}-\d{2}-\d{2})\b",
                                      cells.get("shipped_on_board_date", "")),
        "place_of_issue": _region_value(cells.get("place_and_date_of_issue", "")),
    })
    for region, prefix in (("shipper", "shipper"), ("consignee", "consignee"),
                           ("notify_parties", "notify_party")):
        party = _party_values(cells.get(region, ""), region)
        fields.update({f"{prefix}_{key}": value for key, value in party.items()})
    vessel = cells.get("vessel_and_voyage", "")
    vessel_line = _region_value(vessel) or ""
    vessel_match = re.fullmatch(r"(.+?)\s*-\s*(\d+)", vessel_line)
    fields["vessel"] = vessel_match.group(1) if vessel_match else (vessel_line or None)
    fields["voyage"] = vessel_match.group(2) if vessel_match else None
    row = {
        "container_no": _match(r"\b([A-Z]{4}\d{7})\b", cargo1),
        "seal_no": _match(r"(?:Seal Number|Seal)\s*:?\s*([A-Z0-9]+)", cargo1),
        "marks": _match(r"Marks and Numbers\s*:?\s*\n([^\n]+)", cargo1),
        "number_of_packages": int(v) if (v := _match(r"(\d+)\s+Package\(s\)", cargo2)) else None,
        "hs_code": _match(r"H\.?S\.?\s*(\d{8})", cargo2),
        "gross_weight": int(v.replace(",", "")) if (v := _match(r"([\d,]+)\s*kgs", weight)) else None,
        "measurement": float(v) if (v := _match(r"(\d+(?:\.\d+)?)\s*cu\.?\s*m", measure)) else None,
    }
    row.update({
        "seal_number": row["seal_no"],
        "package_type": _match(r"\b(PACKAGES)\b", cargo1),
        "general_description": _match(r"Package\(s\)\s+of\s+([^\n]+)", cargo2),
        "gross_weight_unit": _match(r"[\d,]+\s*(kgs)\b", weight),
        "measurement_unit": _match(r"\d+(?:\.\d+)?\s*(cu\.?\s*m\.?)", measure),
    })
    return {
        "template": "hemisphere_bill_of_lading_alt_2",
        "fields": fields,
        "containers": [row] if row["container_no"] else [],
        "freight_charges": [],
        "totals": {
            "gross_weight": _match(r"([\d,]+)\s*kgs", cells.get("weight_total", "")),
            "measurement": _match(r"(\d+(?:\.\d+)?)\s*cu\.?\s*m", cells.get("measurement_total", "")),
        },
        "source_cells": cells,
    }


def verify(run_dir: Path) -> dict[str, Any]:
    ocr_path = run_dir / "pages/page-001/segments/structured-ocr.json"
    record = json.loads(ocr_path.read_text())
    cells = {name: str(value) for block in record["blocks"] for name, value in block["cells"].items()}
    parsed = parse_cells(cells)
    output = run_dir / "candidate"
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "bill_of_lading_fields.json", parsed)
    failures = []
    if len(parsed["containers"]) != 1:
        failures.append("expected one cargo row")
    if not parsed["fields"]["imo_number"]:
        failures.append("IMO number missing from discharge-agent crop")
    if not parsed["fields"]["port_of_discharge_agent_name"]:
        failures.append("discharge agent name missing")
    if parsed["fields"]["port_of_discharge_agent_name"] == parsed["fields"]["imo_number"]:
        failures.append("IMO number was assigned as the agent name")
    if re.search(r"\bBRITAIN\b", cells.get("place_of_delivery", ""), re.I) and not re.search(
            r"\bBRITAIN\b", cells.get("place_of_receipt", ""), re.I):
        failures.append("BRITAIN appears in delivery but not receipt; review association")
    if cells.get("charges_body", "").strip():
        failures.append("freight charges body is expected to be blank")
    for path in (run_dir / "pages/page-001/final.html", output / "document.md"):
        if not path.is_file():
            failures.append(f"missing {path.relative_to(run_dir)}")
    report = {
        "status": "passed" if not failures else "failed", "row_count": len(parsed["containers"]),
        "failures": failures, "source_ocr": str(ocr_path.relative_to(run_dir)),
        "parsed_fields": "candidate/bill_of_lading_fields.json",
        "scope": "template structure and source association; visual review is separate",
    }
    atomic_json(output / "bill_of_lading_verification.json", report)
    qc_path = run_dir / "qc-report.json"
    qc = json.loads(qc_path.read_text())
    qc["field_verification"] = {"status": report["status"], "row_count": report["row_count"],
                                "report": "candidate/bill_of_lading_verification.json"}
    if failures:
        qc["status"] = "failed"
        qc.setdefault("structural_errors", []).append({"issue": "alt2_field_verification_failed", "errors": failures})
    atomic_json(qc_path, qc)
    return report
