"""One-page PyMuPDF + LLM table-spec experiment using copied local inputs."""

from __future__ import annotations

import base64
import argparse
import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import anthropic
import pymupdf


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "inputs" / "bendamustine-page-001.pdf"
REFERENCE = ROOT / "inputs" / "bendamustine-table-001-reference.json"
OUT = ROOT / "results" / "bendamustine-table-spec-poc"
MODEL = os.environ.get("TABLE_SPEC_MODEL", "claude-sonnet-5-5")
HEADERS = ["Preference", "Requires Prior Auth", "Drug Name", "HCPCS Code", "Description"]


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def parse_json(value: str) -> dict:
    value = value.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--call-model", action="store_true", help="Send the crop and extracted evidence to Claude")
    parser.add_argument("--verify-existing", action="store_true", help="Recheck the saved spec locally without an API call")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    times: dict[str, float] = {}
    started = time.perf_counter()
    with pymupdf.open(PDF) as doc:
        page = doc[0]
        tables = page.find_tables().tables
        if not tables:
            raise RuntimeError("PyMuPDF found no table")
        table = tables[0]
        # PyMuPDF also joins the following bullet list to this table. Stop at
        # the last row containing the five actual drug entries.
        row_data = table.extract()
        last_data_row = next(i for i, row in enumerate(row_data) if any("J9056" in str(cell) for cell in row))
        rect = pymupdf.Rect(table.bbox[0], table.bbox[1], table.bbox[2], table.rows[last_data_row].bbox[3])
        rect += (-4, -4, 4, 0)
        words = [
            {"text": w[4], "box": [round(n, 1) for n in w[:4]]}
            for w in page.get_text("words", clip=rect, sort=True)
        ]
        native_text = page.get_text("text", clip=rect, sort=True)
        png = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect, alpha=False).tobytes("png")
        evidence = {
            "source_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
            "page": 1,
            "box_pt": [round(n, 2) for n in rect],
            "native_text": native_text,
            "words": words,
            "raw_pymupdf_grid": row_data[: last_data_row + 1],
        }
        (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
        (OUT / "table-crop.png").write_bytes(png)
    times["pymupdf_evidence_ms"] = round((time.perf_counter() - started) * 1000, 2)
    if not args.call_model and not args.verify_existing:
        print(json.dumps({"evidence": str(OUT / "evidence.json"), "crop": str(OUT / "table-crop.png"),
                          "native_word_count": len(words), "raw_grid_rows": len(row_data),
                          "selected_data_rows": last_data_row - 1,
                          "timings_ms": times}, indent=2))
        return

    if args.verify_existing:
        spec = json.loads((OUT / "table-spec.json").read_text())
        rows = spec["rows"]
        response = None
    else:
        prompt = (
        "Create a structured specification of ONLY the five-column drug table in the attached PDF crop. "
        "Use the image for cell boundaries and the PyMuPDF word coordinates and raw grid as evidence. "
        "The raw grid has spurious empty columns and a following bullet list; exclude both. "
        "Do not use any prior HTML or table JSON. Preserve exact printed values, with whitespace normalized. "
        "Return only JSON with keys headers (array of 5 strings) and rows (array of 5 objects keyed by headers). "
        "Do not infer missing values. Evidence follows:\n"
        + json.dumps({"native_text": native_text, "words": words, "raw_grid": row_data[: last_data_row + 1]}, ensure_ascii=False)
        )
        call_started = time.perf_counter()
        response = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode("ascii")}},
        ]}],
        )
        times["llm_ms"] = round((time.perf_counter() - call_started) * 1000, 2)
        answer = "".join(block.text for block in response.content if block.type == "text")
        spec_body = parse_json(answer)
        if spec_body.get("headers") != HEADERS:
            raise ValueError(f"Unexpected headers: {spec_body.get('headers')}")
        rows = spec_body.get("rows")
    if not isinstance(rows, list) or len(rows) != 5 or any(set(row) != set(HEADERS) for row in rows):
        raise ValueError("Expected five rows with precisely the five headers")
    if not args.verify_existing:
        spec = {
            "schema_version": 1,
            "document_id": "geha-coverage-policy-bendamustine",
            "source_sha256": evidence["source_sha256"],
            "page": 1,
            "box_pt": evidence["box_pt"],
            "headers": HEADERS,
            "rows": rows,
            "evidence": "PyMuPDF words, grid, and table crop",
            "model": MODEL,
        }
        (OUT / "table-spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")

    verify_started = time.perf_counter()
    normalized_text = normalized(native_text)
    source_checks = []
    for row_number, row in enumerate(rows, 1):
        for header in HEADERS:
            value = str(row[header])
            # Checking individual cells against the source catches fabricated
            # text, while the reference comparison below checks relationships.
            extracted_row = normalized(" ".join(str(cell or "") for cell in row_data[row_number + 1]))
            found = normalized(value) in normalized_text or normalized(value) in extracted_row
            source_checks.append({"row": row_number, "column": header, "value": value,
                                  "found_in_pdf_text": found})
    reference = json.loads(REFERENCE.read_text())
    ref_rows = reference["rows"]
    differences = []
    for number, (actual, expected) in enumerate(zip(rows, ref_rows), 1):
        for header in HEADERS:
            if normalized(str(actual[header])) != normalized(str(expected[header])):
                differences.append({"row": number, "column": header,
                                    "generated": actual[header], "reference": expected[header]})
    times["verification_ms"] = round((time.perf_counter() - verify_started) * 1000, 2)
    times["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
    report = {
        "model": MODEL,
        "source_checks_passed": sum(c["found_in_pdf_text"] for c in source_checks),
        "source_checks_total": len(source_checks),
        "source_check_failures": [c for c in source_checks if not c["found_in_pdf_text"]],
        "reference_cells_matched": len(HEADERS) * len(rows) - len(differences),
        "reference_cells_total": len(HEADERS) * len(rows),
        "reference_differences": differences,
        "timings_ms": times,
        "token_usage": ({"input": response.usage.input_tokens, "output": response.usage.output_tokens}
                        if response is not None else None),
        "reference_review_status": reference.get("review_status"),
    }
    if args.verify_existing:
        (OUT / "validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    else:
        (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
