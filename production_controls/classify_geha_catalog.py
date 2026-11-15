#!/usr/bin/env python3
"""Classify the GEHA live catalog for human review.

This intentionally does not define storage/object-key paths. It creates a
review inventory from collections/inventory-snapshot.json so the taxonomy can
be validated before the S3 key schema is finalized.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path("/Users/dc/geha")
SNAPSHOT = ROOT / "collections" / "inventory-snapshot.json"
OUT_DIR = ROOT / "production_controls"
JSON_OUT = OUT_DIR / "geha-document-classification.json"
CSV_OUT = OUT_DIR / "geha-document-classification.csv"
SUMMARY_OUT = OUT_DIR / "geha-document-classification-summary.json"


YEAR_RE = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
DATE_SUFFIX_RE = re.compile(r"(?:-|_)(20\d{2})(0\d|1[0-2])([0-3]\d)(?:\.[^.]+)?$")


def slug(text: str) -> str:
    text = unquote(text).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text


def year_from(title: str, path: str) -> str | None:
    # Prefer years explicitly present in the asset's URL or title.
    matches = YEAR_RE.findall(f"{path} {title}")
    return matches[-1] if matches else None


def classify(asset: dict) -> dict:
    title = asset.get("title") or ""
    url = asset.get("url") or ""
    path = unquote(urlparse(url).path).lower()
    text = f"{title} {path}".lower()
    normalized = slug(title)

    language = "Spanish" if re.search(r"(?:-sp\b|\bspanish\b|_sp\b)", text) else "English"
    explicit_year = year_from(title, path)
    revision_hint = None
    revision_source = "not_applicable"
    if "/coverage-policies/" in path:
        m = DATE_SUFFIX_RE.search(path.rsplit("/", 1)[-1])
        if m:
            revision_hint = "-".join(m.groups())
            revision_source = "explicit_url_date"
        else:
            revision_source = "embedded_pdf_required"
    elif explicit_year:
        revision_hint = explicit_year
        revision_source = "plan_year_or_title_year"

    program = "general"
    if "/dental/" in path or " dental " in f" {text} ":
        program = "dental"
    elif "/vision/" in path or "vision plan brochure" in text:
        program = "vision"
    elif "/prescriptions/" in path or "prescription" in text:
        program = "prescription"
    elif "/medical/" in path or any(k in text for k in ("fehb", "pshb", "medical plan", "medical benefits")):
        program = "medical"
    elif "/coverage-policies/" in path:
        program = "medical"

    if "/coverage-policies/" in path:
        doc_type = "coverage_policy"
        reason = "URL is under GEHA coverage-policies"
    elif "/claims/" in path:
        doc_type = "claims_form"
        reason = "URL is under claims"
    elif "/appeals/" in path:
        doc_type = "appeals_or_notice"
        reason = "URL is under appeals"
    elif "/prescriptions/" in path:
        doc_type = "prescription_form"
        reason = "URL is under prescriptions"
    elif "/print/" in path:
        if "den" in normalized or program == "dental":
            doc_type = "dental_form"
        else:
            doc_type = "member_form"
        reason = "UMF/member print form URL"
    elif "summary-of-benefits-and-coverage" in text or re.search(r"\bsbc\b", text):
        doc_type = "medical_summary_of_benefits"
        reason = "Title/URL identifies a Summary of Benefits and Coverage"
    elif program == "dental" and "benefits guide" in text:
        doc_type = "dental_benefits_guide"
        reason = "Dental benefits guide"
    elif program == "dental" and ("plan brochure" in text or "brochure" in text):
        doc_type = "dental_plan_brochure"
        reason = "Dental plan brochure"
    elif program == "medical" and "benefits guide" in text:
        doc_type = "medical_benefits_guide"
        reason = "Medical benefits guide"
    elif program == "medical" and ("plan brochure" in text or "brochure" in text):
        doc_type = "medical_plan_brochure"
        reason = "Medical plan brochure"
    elif program == "vision" and "brochure" in text:
        doc_type = "vision_plan_brochure"
        reason = "Vision plan brochure"
    elif program == "dental" and ("cdplus" in normalized or "coordination of benefits" in text or "dentist nomination" in text):
        doc_type = "dental_form"
        reason = "Dental-specific form"
    elif "medicare reimbursement account claims form" in text:
        doc_type = "claims_form"
        reason = "Medicare reimbursement claims form"
    elif "enrollment" in text:
        doc_type = "enrollment_form"
        reason = "Enrollment form"
    elif "advance care" in text or "member rights" in text:
        doc_type = "member_resource"
        reason = "Member resource"
    elif "form" in text:
        doc_type = "other_form"
        reason = "Form identified from title/URL"
    else:
        doc_type = "other_document"
        reason = "No high-confidence type pattern matched"

    # A family key is only a review aid; it is not the future S3 object key.
    family = normalized
    family = re.sub(r"(?:-20\d{2})", "", family)
    family = re.sub(r"-20\d{6}$", "", family)
    family = re.sub(r"-(?:sp|spanish)$", "", family)
    family = re.sub(r"-(?:brochure|guide|form|sbc)$", "", family)
    family = family.strip("-") or normalized

    review_flags: list[str] = []
    if revision_source == "embedded_pdf_required":
        review_flags.append("extract_revision_from_pdf")
    if doc_type in {"other_document", "other_form"}:
        review_flags.append("confirm_document_type")
    if not explicit_year and doc_type in {"medical_plan_brochure", "medical_benefits_guide", "medical_summary_of_benefits", "dental_plan_brochure", "dental_benefits_guide"}:
        review_flags.append("confirm_year")
    if asset.get("rawPath") is None:
        review_flags.append("not_downloaded_to_crawl_dir")
    processing_status = asset.get("processing")
    if isinstance(processing_status, dict):
        processing_status = processing_status.get("status")
    qc_status = asset.get("qc")
    if isinstance(qc_status, dict):
        qc_status = qc_status.get("status")
    if processing_status in {"failed", "mismatch", "visual_review"} or qc_status in {"failed", "mismatch", "visual_review"}:
        review_flags.append("processing_attention")

    return {
        "id": asset.get("id"),
        "title": title,
        "source_url": url,
        "collection": asset.get("collection"),
        "catalog_family": asset.get("family"),
        "document_family_review_key": family,
        "program": program,
        "document_type": doc_type,
        "language": language,
        "plan_year": explicit_year if program in {"medical", "dental", "vision"} and doc_type not in {"coverage_policy"} else None,
        "revision_hint": revision_hint,
        "revision_source": revision_source,
        "classification_reason": reason,
        "review_flags": review_flags,
        "raw_path": asset.get("rawPath"),
        "catalog_status": asset.get("status"),
        "processing_status": processing_status,
        "qc_status": qc_status,
        "promoted": asset.get("promoted"),
    }


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text())
    rows = [classify(asset) for asset in snapshot.get("assets", [])]
    rows.sort(key=lambda r: (r["program"], r["document_type"], r["plan_year"] or "", r["title"].lower()))

    summary = {
        "source_snapshot": str(SNAPSHOT),
        "root_url": snapshot.get("rootUrl"),
        "snapshot_created_at": snapshot.get("createdAt"),
        "total_documents": len(rows),
        "by_document_type": dict(sorted(Counter(r["document_type"] for r in rows).items())),
        "by_program": dict(sorted(Counter(r["program"] for r in rows).items())),
        "by_plan_year": dict(sorted(Counter(r["plan_year"] or "not_applicable_or_unknown" for r in rows).items())),
        "by_language": dict(sorted(Counter(r["language"] for r in rows).items())),
        "needs_review": sum(bool(r["review_flags"]) for r in rows),
        "review_flag_counts": dict(sorted(Counter(flag for r in rows for flag in r["review_flags"]).items())),
        "note": "This taxonomy is for review only. It does not define S3 object keys or replace PDF-level revision extraction.",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps({"summary": summary, "documents": rows}, indent=2) + "\n")
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n")
    fields = list(rows[0].keys()) if rows else []
    with CSV_OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["review_flags"] = ";".join(flat["review_flags"])
            writer.writerow(flat)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {JSON_OUT}")
    print(f"Wrote {CSV_OUT}")
    print(f"Wrote {SUMMARY_OUT}")


if __name__ == "__main__":
    main()
