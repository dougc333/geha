#!/usr/bin/env python3
"""Draft a bill-of-lading parser spec from a PDF page and blocking prompt.

The result is a review candidate, not a replacement for bill_of_lading_spec.json.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path

import pymupdf
from openai import OpenAI
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
DEFAULT_PDF = HERE.parent / "blocking_demo/bill_of_lading_alt_1.pdf"
DEFAULT_PROMPT = HERE.parent / "blocking_demo/interactive/prompt.md"
DEFAULT_OUTPUT = HERE / "spec_candidate"


def validate_spec(spec: dict, width: int, height: int) -> list[str]:
    """Reject malformed parser contracts; return review warnings for uncertain rules."""
    errors: list[str] = []
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if not isinstance(spec.get("template"), str) or not spec["template"]:
        errors.append("template must be a nonempty string")
    if spec.get("page_size_px") != [width, height]:
        errors.append(f"page_size_px must be {[width, height]}")
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or [b.get("block") for b in blocks if isinstance(b, dict)] != list(range(1, 9)):
        errors.append("blocks must be numbered 1 through 8 in order")
        blocks = blocks if isinstance(blocks, list) else []
    field_names: set[str] = set()
    for block in blocks:
        if not isinstance(block, dict):
            errors.append("each block must be an object")
            continue
        box = block.get("box_px")
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) and not isinstance(v, bool) for v in box)):
            errors.append(f"block {block.get('block')}: box_px must be four integers")
        elif not (0 <= box[0] < width and 0 <= box[1] < height and 0 < box[2] <= width - box[0] and 0 < box[3] <= height - box[1]):
            errors.append(f"block {block.get('block')}: box_px is outside the page")
        if not isinstance(block.get("fields"), list):
            errors.append(f"block {block.get('block')}: fields must be a list")
            continue
        for field in block["fields"]:
            if not isinstance(field, dict) or not isinstance(field.get("name"), str):
                errors.append(f"block {block.get('block')}: invalid field")
                continue
            field_names.add(field["name"])
            if not any(field.get(key) for key in ("label", "label_re", "find")):
                errors.append(f"{field['name']}: needs label, label_re, or find")
            for key in ("pattern", "label_re", "find"):
                if field.get(key):
                    try:
                        re.compile(field[key])
                    except (re.error, TypeError) as exc:
                        errors.append(f"{field['name']}.{key}: invalid regex: {exc}")
            if field.get("type", "string") not in {"string", "int", "date"}:
                errors.append(f"{field['name']}: unsupported type")
    groups = spec.get("groups")
    if not isinstance(groups, list) or not groups or not any(g.get("name") == "containers" and g.get("block") == 6 for g in groups if isinstance(g, dict)):
        errors.append("groups must include containers from block 6")
    else:
        for group in groups:
            if group.get("name") == "containers":
                required_cargo = {"container_no", "seal_no", "marks", "packages", "commodity",
                                  "hs_code", "set_temp", "gross_weight_kg", "measurement_cbm"}
                actual_cargo = {field.get("name") for field in group.get("fields", []) if isinstance(field, dict)}
                if not required_cargo <= actual_cargo:
                    errors.append(f"containers group missing {sorted(required_cargo - actual_cargo)}")
            for field in group.get("fields", []):
                name = field.get("name")
                field_names.add(name)
                if not isinstance(field.get("find"), str):
                    errors.append(f"{name}: group field needs find regex")
                else:
                    try:
                        re.compile(field["find"])
                    except re.error as exc:
                        errors.append(f"{name}.find: invalid regex: {exc}")
    if not isinstance(spec.get("rules"), list):
        errors.append("rules must be a list")
    else:
        for rule in spec["rules"]:
            if rule.get("check") not in {"group_sum_equals", "words_match_digit", "valid_date"}:
                errors.append(f"unsupported rule check: {rule.get('check')}")
            if rule.get("field") not in field_names:
                errors.append(f"rule {rule.get('name')}: unknown field {rule.get('field')}")
    if errors:
        raise ValueError("Candidate spec validation failed:\n- " + "\n- ".join(errors))
    return ["Field optionality and cross-field rules need review across additional forms.",
            "Cargo row association is order-based; inspect both rows on the page."]


def response_schema() -> dict:
    """Constrain the model to the exact parser contract, including repeated groups."""
    def obj(properties: dict) -> dict:
        return {"type": "object", "additionalProperties": False,
                "properties": properties, "required": list(properties)}

    string = {"type": "string"}
    integer = {"type": "integer"}
    boolean = {"type": "boolean"}
    box = {"type": "array", "items": integer}
    field = obj({"name": string, "label": string, "label_re": string,
                 "pattern": string, "find": string, "type": string,
                 "required": boolean, "kind": string, "line": boolean})
    group_field = obj({"name": string, "find": string, "type": string, "check": string})
    block = obj({"block": integer, "name": string, "box_px": box,
                 "constants": {"type": "array", "items": string},
                 "fields": {"type": "array", "items": field}})
    group = obj({"name": string, "block": integer, "note": string,
                 "fields": {"type": "array", "items": group_field}})
    rule = obj({"name": string, "check": string, "group": string,
                "field": string, "equals": string, "message": string})
    return obj({"schema_version": integer, "template": string, "description": string,
                "page_size_px": box, "blocks": {"type": "array", "items": block},
                "groups": {"type": "array", "items": group},
                "rules": {"type": "array", "items": rule}})


def normalize_spec(spec: dict) -> dict:
    """Remove placeholder keys required by strict model output but unused by parser."""
    for block in spec["blocks"]:
        for field in block["fields"]:
            for key in ("label", "label_re", "pattern", "find", "kind"):
                if not field[key]:
                    del field[key]
            if field["type"] == "string":
                del field["type"]
            if not field["line"]:
                del field["line"]
        if not block["constants"]:
            del block["constants"]
    for group in spec["groups"]:
        for field in group["fields"]:
            if field["type"] == "string":
                del field["type"]
            if not field["check"]:
                del field["check"]
    for rule in spec["rules"]:
        for key in ("group", "equals"):
            if not rule[key]:
                del rule[key]
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--page", type=int, default=1, help="One-based PDF page number")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--reference-spec", type=Path,
                        help="Approved spec to send as an explicit format and geometry reference")
    parser.add_argument("--response-json", type=Path,
                        help="Recheck a saved model response locally, without an API call")
    args = parser.parse_args()
    pdf = args.pdf.expanduser().resolve()
    prompt = args.prompt.expanduser().resolve()
    reference = args.reference_spec.expanduser().resolve() if args.reference_spec else None
    output = args.output_dir.expanduser().resolve()
    if not pdf.is_file() or not prompt.is_file():
        parser.error("PDF and prompt must both exist")
    if reference is not None and not reference.is_file():
        parser.error(f"Reference spec does not exist: {reference}")
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output directory is not empty: {output}")
    with pymupdf.open(pdf) as document:
        if not 1 <= args.page <= len(document):
            parser.error(f"Page must be between 1 and {len(document)}")
        pixmap = document[args.page - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        image_bytes = pixmap.tobytes("png")
        width, height = pixmap.width, pixmap.height
    output.mkdir(parents=True, exist_ok=True)
    source_png = output / "source.png"
    source_png.write_bytes(image_bytes)
    if args.response_json:
        raw_text = args.response_json.expanduser().resolve().read_text(encoding="utf-8")
        response_id = None
    else:
        response = OpenAI(max_retries=2, timeout=180).responses.create(
            model=args.model,
            store=False,
            instructions=(
            "Inspect this bill-of-lading page and the user's blocking prompt. Draft a reusable "
            "parser spec compatible with bol_parser.py. Follow the supplied output JSON schema. "
            "If a human-authored reference spec is included, preserve its parser field names, "
            "supported checks and coordinate semantics; inspect the page to verify them. "
            "Keep all nine cargo group fields: container_no, seal_no, marks, packages, commodity, "
            "hs_code, set_temp, gross_weight_kg, measurement_cbm. Return eight numbered "
            "blocks. For box_px use [x,y,width,height], NOT [x1,y1,x2,y2]. The final width and "
            "height are extents, never bottom-right coordinates. "
            "For unused string properties use an empty string. For unused required use false; "
            "for unused line use false. Include groups with one named containers from block 6. "
            "Define field names, label anchors, regex patterns, types (string, int, date), "
            "and required flags. Use regex capture groups for repeated cargo fields. Only "
            "use only these supported rule checks: group_sum_equals, words_match_digit, "
            "valid_date. Do not place shipment-specific values inside rules or patterns. Do not place shipment "
            "values such as container numbers or weights in the spec. The prompt's seven/eight "
            "inconsistency resolves to eight blocks. Match coordinates to this image's pixel "
            f"size of {width} by {height}. This is a draft for review, not an approved spec."
            ),
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": "Blocking prompt:\n" + prompt.read_text(encoding="utf-8")},
                *([{"type": "input_text", "text": "Human-authored reference spec:\n" + reference.read_text(encoding="utf-8")}]
                  if reference is not None else []),
                {"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode(), "detail": "high"},
            ]}],
            text={"format": {"type": "json_schema", "name": "bol_candidate_spec", "strict": True,
                             "schema": response_schema()}},
        )
        raw_text = response.output_text
        response_id = response.id
    (output / "model_response_raw.json").write_text(raw_text.rstrip() + "\n", encoding="utf-8")
    spec = normalize_spec(json.loads(raw_text))
    (output / "candidate_spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        warnings = validate_spec(spec, width, height)
        status, errors = "candidate_needs_review", []
    except ValueError as exc:
        status, errors, warnings = "invalid_candidate", str(exc).splitlines()[1:], []
    with Image.open(source_png) as image:
        overlay = image.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for block in spec["blocks"]:
        x, y, w, h = block["box_px"]
        draw.rectangle((x, y, x + w, y + h), outline="red", width=3)
        draw.text((x + 6, y + 6), f"{block['block']}: {block.get('name', '')}", fill="red", stroke_width=2, stroke_fill="white")
    overlay.save(output / "candidate_overlay.png")
    (output / "generation_report.json").write_text(json.dumps({
        "status": status, "source_pdf": str(pdf), "page": args.page,
        "prompt": str(prompt),
        "reference_spec_sent": str(reference) if reference and not args.response_json else None,
        "model": args.model, "response_id": response_id,
        "candidate_spec": "candidate_spec.json", "overlay": "candidate_overlay.png",
        "validation_errors": errors, "warnings": warnings,
    }, indent=2) + "\n", encoding="utf-8")
    print(output / "candidate_spec.json")


if __name__ == "__main__":
    main()
