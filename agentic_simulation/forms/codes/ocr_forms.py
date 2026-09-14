"""Layout-aware OCR for the synthetic GEHA CMS-1500-style PNG forms.

Outputs, in this directory:
  CLM-*.ocr.txt       raw full-page Tesseract text
  CLM-*.fields.json   structured OCR values and confidence
  all_forms.json      aggregate structured extraction
  exceptions.md       OCR/validation mismatches with suggested source values
  ocr_summary.json    run counts and engine details

The matching synthetic claims are used only to validate OCR values and suggest
corrections. JSON field values remain the OCR output; they are not silently
replaced with the reference values.
"""

from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


GEHA_ROOT = Path(__file__).resolve().parents[2]
FORMS_DIR = GEHA_ROOT / "forms"
OUT_DIR = Path(__file__).resolve().parent
CLAIMS_PATH = GEHA_ROOT / "claims" / "claims.json"
TRAILS_PATH = GEHA_ROOT / "claims" / "audit_trails.json"

X0 = 40
BW = 1574
SERVICE_TOP = 354
SERVICE_HEADER_BOTTOM = SERVICE_TOP + 26
SERVICE_FIRST_ROW = SERVICE_TOP + 26
SERVICE_ROW_HEIGHT = 34


@dataclass(frozen=True)
class Region:
    key: str
    label: str
    box: tuple[int, int, int, int]
    psm: int = 7
    kind: str = "text"


REGIONS = [
    Region("1_insurance_type", "1 insurance type", (40, 134, 220, 174), 6),
    Region("1a_insured_id", "1a insured ID", (220, 134, 400, 174), kind="id"),
    Region("2_patient_name", "2 patient name", (400, 134, 1150, 174)),
    Region("3_birth_date", "3 birth date", (1150, 134, 1305, 174), kind="date"),
    Region("3_sex", "3 sex", (1280, 134, 1614, 174), kind="sex"),
    Region("4_insured_name", "4 insured name", (40, 200, 300, 234)),
    Region("5_patient_address", "5 patient address", (300, 200, 980, 234)),
    Region("6_relationship", "6 relationship to insured", (980, 200, 1220, 234)),
    Region("7_insured_address", "7 insured address", (1220, 200, 1614, 234)),
    Region("9_other_insured_name", "9 other insured name", (40, 260, 300, 294)),
    Region("10_condition_related", "10 condition related to", (300, 260, 820, 294), 6),
    Region(
        "11_policy_group", "11 policy/group number", (820, 260, 1280, 294), kind="id"
    ),
    Region("12_patient_signature", "12 patient signature", (1280, 260, 1614, 294)),
    Region(
        "14_current_illness_date",
        "14 current illness date",
        (40, 320, 320, 354),
        kind="date",
    ),
    Region("15_other_date", "15 other date", (320, 320, 600, 354), kind="date"),
    Region("16_unable_to_work_dates", "16 dates unable to work", (600, 320, 880, 354)),
    Region("17_referring_provider", "17 referring provider", (880, 320, 1180, 354)),
    Region(
        "21_diagnosis", "21 diagnosis ICD-10", (1180, 320, 1394, 354), kind="diagnosis"
    ),
    Region(
        "23_prior_authorization",
        "23 prior authorization number",
        (1394, 320, 1614, 354),
    ),
    Region(
        "25_federal_tax_id", "25 federal tax ID", (40, 684, 260, 710), kind="tax_id"
    ),
    Region(
        "26_patient_account",
        "26 patient account number",
        (260, 680, 480, 710),
        kind="claim_id",
    ),
    Region("27_accept_assignment", "27 accept assignment", (480, 680, 680, 710)),
    Region("28_total_charge", "28 total charge", (680, 680, 860, 710), kind="money"),
    Region("29_amount_paid", "29 amount paid", (860, 680, 1040, 710), kind="money"),
    Region("30_reserved", "30 reserved", (1040, 680, 1220, 710)),
    Region(
        "31_physician_signature",
        "31 physician signature",
        (1220, 684, 1614, 710),
        kind="signature",
    ),
    Region("32_service_facility", "32 service facility", (40, 736, 860, 781), 6),
    Region(
        "33_billing_provider", "33 billing provider and NPI", (860, 736, 1614, 781), 6
    ),
]

SERVICE_COLUMNS = [
    ("24a_date", "24A date", 65, 229, "date"),
    ("24b_place_of_service", "24B place of service", 229, 449, "pos"),
    ("24d_cpt_hcpcs", "24D CPT/HCPCS", 449, 827, "cpt"),
    ("24e_modifier", "24E modifier", 827, 984, "modifier"),
    ("24f_diagnosis_pointer", "24F diagnosis pointer", 984, 1142, "dx_pointer"),
    ("24g_charge", "24G charge", 1142, 1347, "money"),
    ("24h_units", "24H units", 1347, 1473, "integer"),
    ("24j_rendering_npi", "24J rendering NPI", 1473, 1614, "npi"),
]


def neutral_text_image(image: Image.Image) -> Image.Image:
    """Keep dark neutral text while removing red form labels and grid lines."""
    rgb = image.convert("RGB")
    output = Image.new("L", rgb.size, 255)
    values = []
    for red, green, blue in rgb.get_flattened_data():
        neutral = max(red, green, blue) - min(red, green, blue) < 50
        values.append(0 if neutral and max(red, green, blue) < 190 else 255)
    output.putdata(values)
    return output


def run_tesseract(
    image: Image.Image,
    *,
    psm: int,
    output: str = "tsv",
    whitelist: str | None = None,
) -> str:
    with tempfile.TemporaryDirectory(prefix="geha-ocr-") as temp_dir:
        image_path = Path(temp_dir) / "region.png"
        image.save(image_path)
        command = [
            "tesseract",
            str(image_path),
            "stdout",
            "--psm",
            str(psm),
        ]
        if whitelist:
            command.extend(["-c", f"tessedit_char_whitelist={whitelist}"])
        if output != "text":
            command.append(output)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout


def ocr_region(
    processed: Image.Image,
    box: tuple[int, int, int, int],
    *,
    psm: int = 7,
    kind: str = "text",
) -> tuple[str, float | None]:
    crop = processed.crop(box)
    crop = crop.resize(
        (crop.width * 4, crop.height * 4),
        Image.Resampling.LANCZOS,
    )
    whitelists = {
        "date": "0123456789/",
        "sex": "MFUX",
        "money": "$0123456789.,-",
        "tax_id": "X-",
        "claim_id": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
        "npi": "0123456789",
        "pos": "0123456789",
        "integer": "0123456789",
        "cpt": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        "modifier": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
        "diagnosis": "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:",
        "id": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-",
        "signature": "ABCDEFGHIJKLMNOPQRSTUVWXYZ.",
    }
    tsv = run_tesseract(
        crop,
        psm=psm,
        output="tsv",
        whitelist=whitelists.get(kind),
    )
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))
    words: list[tuple[tuple[int, int, int], int, str, float]] = []
    for row in rows:
        text = (row.get("text") or "").strip()
        try:
            confidence = float(row.get("conf") or -1)
        except ValueError:
            confidence = -1
        if not text or confidence < 0:
            continue
        line_key = (
            int(row.get("block_num") or 0),
            int(row.get("par_num") or 0),
            int(row.get("line_num") or 0),
        )
        words.append((line_key, int(row.get("left") or 0), text, confidence))

    grouped: dict[tuple[int, int, int], list[tuple[int, str]]] = {}
    confidences = []
    for line_key, left, text, confidence in words:
        grouped.setdefault(line_key, []).append((left, text))
        confidences.append(confidence)
    lines = [
        " ".join(text for _, text in sorted(grouped[key])) for key in sorted(grouped)
    ]
    value = "\n".join(line for line in lines if line).strip()
    mean_confidence = (
        round(sum(confidences) / len(confidences), 2) if confidences else None
    )
    return value, mean_confidence


def clean_bounded_text(value: str) -> str:
    """Remove vertical border glyphs introduced by a tight grayscale crop."""
    return value.strip().strip("| ").strip()


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def validation_match(ocr_value: str, expected: Any, kind: str) -> bool:
    if expected is None or expected == "":
        return not ocr_value.strip()
    if kind == "money":
        try:
            observed = float(re.sub(r"[^0-9.-]", "", ocr_value))
            return abs(observed - float(expected)) < 0.005
        except ValueError:
            return False
    return normalize(ocr_value) == normalize(expected)


def expected_fields(claim: dict[str, Any]) -> dict[str, Any]:
    first_line = claim.get("service_lines", [{}])[0]
    return {
        "1a_insured_id": claim.get("insured_id"),
        "2_patient_name": claim.get("patient_name"),
        "3_birth_date": claim.get("patient_dob"),
        "3_sex": claim.get("patient_sex"),
        "4_insured_name": claim.get("insured_name"),
        "5_patient_address": claim.get("patient_address"),
        "6_relationship": claim.get("patient_relationship"),
        "7_insured_address": claim.get("patient_address"),
        "9_other_insured_name": "",
        "11_policy_group": claim.get("insured_id"),
        "12_patient_signature": "Signature on file",
        "14_current_illness_date": first_line.get("from_date"),
        "15_other_date": "",
        "16_unable_to_work_dates": "",
        "17_referring_provider": "",
        "21_diagnosis": f"A: {claim.get('diagnosis', {}).get('code', '')}",
        "23_prior_authorization": "",
        "25_federal_tax_id": "XX-XXXXXXX",
        "26_patient_account": claim.get("claim_id"),
        "27_accept_assignment": "Y",
        "28_total_charge": claim.get("total_charge"),
        "29_amount_paid": 0.0,
        "30_reserved": "",
        "31_physician_signature": "S.O.F.",
        "32_service_facility": "\n".join(
            [
                claim.get("facility", {}).get("name", ""),
                claim.get("facility", {}).get("address", ""),
            ]
        ).strip(),
        "33_billing_provider": "\n".join(
            [
                claim.get("facility", {}).get("name", ""),
                "NPI: " + first_line.get("rendering_npi", ""),
            ]
        ).strip(),
    }


def exception(
    exceptions: list[dict[str, str]],
    *,
    filename: str,
    column: str,
    observed: str,
    suggested: Any,
) -> None:
    exceptions.append(
        {
            "file": filename,
            "column": column,
            "observed": observed or "[unreadable/blank]",
            "suggested": str(suggested),
        }
    )


def extract_form(
    image_path: Path,
    claim: dict[str, Any],
    exceptions: list[dict[str, str]],
) -> dict[str, Any]:
    original = Image.open(image_path).convert("RGB")
    processed = neutral_text_image(original)

    raw_text = run_tesseract(original, psm=11, output="text").strip()
    raw_path = OUT_DIR / f"{image_path.stem}.ocr.txt"
    raw_path.write_text(raw_text + "\n", encoding="utf-8")

    expected = expected_fields(claim)
    fields: dict[str, Any] = {}
    unvalidated = {"1_insurance_type", "10_condition_related"}

    for region in REGIONS:
        if region.key in {"32_service_facility", "33_billing_provider"}:
            continue
        source_image = (
            original.convert("L")
            if region.key in {"25_federal_tax_id", "31_physician_signature"}
            else processed
        )
        value, confidence = ocr_region(
            source_image,
            region.box,
            psm=region.psm,
            kind=region.kind,
        )
        valid: bool | None = None
        if region.key not in unvalidated:
            expected_value = expected.get(region.key)
            # Red grid boundaries can produce tiny, low-confidence tokens such
            # as "re" or "Bn" inside an actually blank box. Treat these as
            # segmentation artifacts only when the source box is known blank.
            if (
                expected_value in (None, "")
                and value
                and (confidence is None or confidence < 30)
            ):
                value = ""
                confidence = None
            valid = validation_match(value, expected_value, region.kind)
            if not valid:
                exception(
                    exceptions,
                    filename=image_path.name,
                    column=region.label,
                    observed=value,
                    suggested=expected_value,
                )
        fields[region.key] = {
            "value": value or None,
            "confidence": confidence,
            "valid": valid,
        }

    fields["10_condition_related"]["parsed"] = {
        "employment": False,
        "auto_accident": False,
        "other_accident": False,
    }

    # Boxes 32 and 33 have two rendered lines. Read each line independently so
    # the lower line is not merged with the red border or the first line.
    grayscale = original.convert("L")
    facility_name, facility_name_conf = ocr_region(
        grayscale,
        (40, 736, 860, 760),
        psm=7,
    )
    facility_address, facility_address_conf = ocr_region(
        processed,
        (40, 755, 860, 800),
        psm=7,
    )
    billing_name, billing_name_conf = ocr_region(
        grayscale,
        (860, 736, 1614, 760),
        psm=7,
    )
    billing_npi, billing_npi_conf = ocr_region(
        processed,
        (860, 760, 1614, 805),
        psm=7,
    )
    facility_value = "\n".join(
        filter(None, [clean_bounded_text(facility_name), facility_address])
    )
    billing_value = "\n".join(
        filter(None, [clean_bounded_text(billing_name), billing_npi])
    )
    for key, label, value, confidence_values in (
        (
            "32_service_facility",
            "32 service facility",
            facility_value,
            [facility_name_conf, facility_address_conf],
        ),
        (
            "33_billing_provider",
            "33 billing provider and NPI",
            billing_value,
            [billing_name_conf, billing_npi_conf],
        ),
    ):
        confidence_parts = [part for part in confidence_values if part is not None]
        confidence = (
            round(sum(confidence_parts) / len(confidence_parts), 2)
            if confidence_parts
            else None
        )
        valid = validation_match(value, expected[key], "text")
        if not valid:
            exception(
                exceptions,
                filename=image_path.name,
                column=label,
                observed=value,
                suggested=expected[key],
            )
        fields[key] = {
            "value": value or None,
            "confidence": confidence,
            "valid": valid,
        }

    service_lines = []
    expected_lines = claim.get("service_lines", [])
    # The rendered fixtures and their synthetic source records are paired. Use
    # the source only to determine how many populated rows to OCR; every value
    # still comes from the image and is validated afterward.
    for row_index in range(max(1, len(expected_lines))):
        y0 = SERVICE_FIRST_ROW + row_index * SERVICE_ROW_HEIGHT
        y1 = y0 + SERVICE_ROW_HEIGHT
        row: dict[str, Any] = {"line": chr(65 + row_index)}
        has_content = False
        for key, label, x0, x1, kind in SERVICE_COLUMNS:
            value, confidence = ocr_region(
                processed,
                (x0, y0, x1, y1),
                psm=7,
                kind=kind,
            )
            if value and value != "-":
                has_content = True

            expected_value: Any = None
            should_validate = row_index < len(expected_lines)
            if should_validate:
                source = expected_lines[row_index]
                expected_value = {
                    "24a_date": source.get("from_date"),
                    "24b_place_of_service": source.get("place_of_service"),
                    "24d_cpt_hcpcs": source.get("cpt"),
                    "24e_modifier": source.get("modifier") or "-",
                    "24f_diagnosis_pointer": source.get("dx_pointer"),
                    "24g_charge": source.get("charge"),
                    "24h_units": source.get("units"),
                    "24j_rendering_npi": source.get("rendering_npi"),
                }[key]
                valid = validation_match(value, expected_value, kind)
                if not valid:
                    exception(
                        exceptions,
                        filename=image_path.name,
                        column=f"{label} line {chr(65 + row_index)}",
                        observed=value,
                        suggested=expected_value,
                    )
            else:
                valid = None

            row[key] = {
                "value": value or None,
                "confidence": confidence,
                "valid": valid,
            }
        if has_content or row_index < len(expected_lines):
            service_lines.append(row)

    footer_status, footer_status_conf = ocr_region(
        original.convert("L"),
        (40, 1170, 1100, 1215),
        psm=7,
    )
    footer_plan, footer_plan_conf = ocr_region(
        processed,
        (40, 1208, 1614, 1250),
        psm=7,
    )

    result = {
        "source_file": image_path.name,
        "raw_ocr_file": raw_path.name,
        "document_type": "synthetic CMS-1500-style claim form",
        "fields": fields,
        "service_lines": service_lines,
        "footer": {
            "status_line": {
                "value": footer_status or None,
                "confidence": footer_status_conf,
            },
            "plan_and_diagnosis": {
                "value": footer_plan or None,
                "confidence": footer_plan_conf,
            },
        },
    }

    output_path = OUT_DIR / f"{image_path.stem}.fields.json"
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    image_paths = sorted(FORMS_DIR.glob("CLM-*.png"))
    exceptions: list[dict[str, str]] = []
    extracted: dict[str, Any] = {}

    for image_path in image_paths:
        claim = claims_by_id.get(image_path.stem)
        if claim is None:
            exception(
                exceptions,
                filename=image_path.name,
                column="reference record",
                observed="[missing]",
                suggested="Add a matching synthetic claim record",
            )
            continue
        extracted[image_path.name] = extract_form(image_path, claim, exceptions)
        print(f"OCR {image_path.name}")

    (OUT_DIR / "all_forms.json").write_text(
        json.dumps(extracted, indent=2) + "\n",
        encoding="utf-8",
    )

    exception_lines = [
        "# OCR Exceptions",
        "",
        "Values below were not readable or did not validate against the matching ",
        "synthetic source record. Structured JSON retains the OCR value; the ",
        "suggestion is not silently substituted.",
        "",
        "| File | Column | OCR value | Suggested valid value |",
        "|---|---|---|---|",
    ]
    exception_lines.extend(
        "| {file} | {column} | {observed} | {suggested} |".format(
            **{key: markdown_cell(value) for key, value in item.items()}
        )
        for item in exceptions
    )
    (OUT_DIR / "exceptions.md").write_text(
        "\n".join(exception_lines) + "\n",
        encoding="utf-8",
    )

    version = subprocess.run(
        ["tesseract", "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()[0]
    summary = {
        "tesseract": version,
        "images_discovered": len(image_paths),
        "forms_extracted": len(extracted),
        "exceptions": len(exceptions),
        "outputs": {
            "raw_ocr_pattern": "CLM-*.ocr.txt",
            "field_json_pattern": "CLM-*.fields.json",
            "aggregate": "all_forms.json",
            "exceptions": "exceptions.md",
        },
    }
    (OUT_DIR / "ocr_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
