"""Per-block JSON Schemas.

Invoices are split into five blocks (header, parties, line_items, totals, extras). The field names follow the
labels in the ocr-mini-bench invoice ground truth (sender_name, receiver_vat, items[].unit_price, ...), so a
merged result has the same shape as that ground truth and can be scored with it.

The Bill of Lading blocks come from the existing versioned spec (`bill_lading/bill_of_lading_spec.json`).
Every schema is strict (`additionalProperties: false`) so it can be used with structured-output APIs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BOL_SPEC = HERE.parents[1] / "bill_lading" / "bill_of_lading_spec.json"

STR = {"type": ["string", "null"]}
NUM = {"type": ["number", "null"]}
DATE = {"type": ["string", "null"], "description": "Date exactly as printed on the document (do not reformat), or null"}


def obj(props: dict[str, dict], required: list[str] | None = None, description: str = "") -> dict[str, Any]:
    return {"type": "object", "description": description, "properties": props,
            "required": required if required is not None else list(props), "additionalProperties": False}


def _described(base: dict, text: str) -> dict:
    return {**base, "description": text}


INVOICE_BLOCKS: dict[str, dict[str, Any]] = {
    "header": obj({
        "invoice_number": _described(STR, "Invoice number exactly as printed"),
        "invoice_date": DATE,
        "due_date": DATE,
        "currency": _described(STR, "ISO currency code, e.g. EUR, USD, GBP"),
        "document_type": _described(STR, "Title of the document if it is not simply 'Invoice' (e.g. 'Tax Invoice'), else null"),
    }, description="Top band: document title, number, dates and currency."),
    "parties": obj({
        "sender_name": STR, "sender_address": STR, "sender_phone": STR, "sender_email": STR, "sender_website": STR,
        "sender_vat": STR, "sender_company_number": STR, "sender_bank_name": STR,
        "sender_bank_account_number": STR, "sender_bic": STR,
        "receiver_name": STR, "receiver_address": STR, "receiver_vat": STR, "receiver_customer_number": STR,
    }, description="Seller (sender) and buyer (receiver) details, including the seller's bank details."),
    "line_items": obj({
        "items": {"type": "array", "items": obj({
            "item_name": STR, "quantity": NUM, "unit_price": NUM, "total_price": NUM,
            "sku": STR, "uom": STR, "discount": NUM, "vat": NUM, "net_price": NUM, "hs_code": STR, "pos": STR,
        }, required=["item_name", "quantity", "unit_price", "total_price"])},
    }, description="The line-item table, one object per row, in printed order."),
    "totals": obj({
        "pretax_amount": NUM, "total_tax_amount": NUM, "tax_rate": _described(NUM, "Percent as a number, e.g. 20 for 20%"),
        "total_amount": NUM, "total_number_of_items": {"type": ["integer", "null"]}, "shipping_charges": NUM,
    }, description="Totals band: subtotal, tax, shipping and grand total."),
    "extras": obj({
        "extras": {"type": "object", "additionalProperties": {"type": ["string", "number", "null"]},
                   "description": "Any other labeled fields (PO reference, payment terms, VIN, project code, ...), keyed by a snake_case label"},
    }, description="Anything labeled that does not belong to the other blocks."),
}

INVOICE_BLOCK_ORDER = ["header", "parties", "line_items", "totals", "extras"]

FAMILIES: dict[str, dict[str, dict[str, Any]]] = {"invoice": INVOICE_BLOCKS}


def bol_blocks(spec_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Per-block schemas for the Meridian Bill of Lading, built from the versioned spec (labels are anchors,
    patterns validate values)."""
    spec = json.loads((spec_path or BOL_SPEC).read_text())
    blocks: dict[str, dict[str, Any]] = {}
    for b in spec["blocks"]:
        props: dict[str, dict] = {}
        required: list[str] = []
        for f in b.get("fields", []):
            p: dict[str, Any] = {"type": ["string", "null"], "description": f"value next to the label '{f.get('label') or f.get('label_re') or f['name']}'"}
            if f.get("pattern"):
                p["pattern"] = f["pattern"]
            props[f["name"]] = p
            if f.get("required"):
                required.append(f["name"])
        blocks[f"{b['block']}_{b['name']}"] = obj(props, required, description=f"Block {b['block']} ({b['name']})")
    return blocks


def merge_invoice(block_results: dict[str, dict]) -> dict[str, Any]:
    """Combine per-block outputs into one record shaped like the benchmark ground truth."""
    out: dict[str, Any] = {}
    h, p, li, t, ex = (block_results.get(k, {}) for k in INVOICE_BLOCK_ORDER)
    out.update({k: v for k, v in h.items()})
    out["sender"] = {k: v for k, v in p.items() if k.startswith("sender_")}
    out["receiver"] = {k: v for k, v in p.items() if k.startswith("receiver_")}
    out["items"] = li.get("items", [])
    out.update({k: v for k, v in t.items()})
    out.update(ex.get("extras", {}))
    return out


def write_schema_files(out_dir: Path | None = None) -> list[Path]:
    out_dir = out_dir or HERE.parent / "schemas"
    written = []
    for family, blocks in {**FAMILIES, "bill_of_lading": bol_blocks()}.items():
        d = out_dir / family
        d.mkdir(parents=True, exist_ok=True)
        for name, schema in blocks.items():
            f = d / f"{name}.schema.json"
            f.write_text(json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": f"{family}/{name}", **schema}, indent=2))
            written.append(f)
    return written


if __name__ == "__main__":
    files = write_schema_files()
    print(f"wrote {len(files)} schema files")
