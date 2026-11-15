"""Runtime quality score: "is the accuracy poor?" without ground truth.

Ground truth does not exist when a document arrives, so accuracy is approximated with deterministic checks that a
wrong extraction tends to fail: required fields present, dates valid, arithmetic that must reconcile, and (for the
Bill of Lading) the spec's value patterns. Each check yields a value in [0, 1] or None when it does not apply.
score = mean of the applicable checks (None if nothing applies). The same inputs always give the same score.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from .schemas import BOL_SPEC

TOL_ABS, TOL_REL = 0.02, 0.01


def _num(x: Any) -> float | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(x)))
    except ValueError:
        return None


def _close(a: float, b: float, tol: float = TOL_ABS) -> bool:
    """Absolute tolerance only. A relative tolerance lets small digit errors on big totals through; the tolerance
    instead grows with the number of rounded terms being summed (pass `tol`)."""
    return abs(a - b) <= tol


CREDIT_KEYS = ("insurance_payment", "insurance_adjustments", "deposit", "amount_paid", "discount_total", "credits", "prepaid")


def _valid_iso(s: Any) -> bool:
    try:
        date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


def _valid_date(s: Any) -> bool:
    """Dates are kept as printed, so accept ISO or a numeric D/M/Y or M/D/Y form (either order is a valid date)."""
    if _valid_iso(s):
        return True
    m = re.fullmatch(r"\s*(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\s*", str(s))
    if not m:
        return False
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return (1 <= a <= 12 and 1 <= b <= 31) or (1 <= b <= 12 and 1 <= a <= 31)


def invoice_checks(rec: dict[str, Any]) -> dict[str, float | None]:
    sender, receiver = rec.get("sender", {}) or {}, rec.get("receiver", {}) or {}
    required = [rec.get("invoice_number"), sender.get("sender_name"), receiver.get("receiver_name"), rec.get("total_amount")]
    checks: dict[str, float | None] = {"required_present": sum(v not in (None, "") for v in required) / len(required)}

    dates = [rec.get(k) for k in ("invoice_date", "due_date") if rec.get(k) not in (None, "")]
    checks["dates_valid"] = sum(_valid_date(d) for d in dates) / len(dates) if dates else None
    if len(dates) == 2 and all(_valid_iso(d) for d in dates):  # order is only checkable for unambiguous ISO dates
        checks["due_after_invoice"] = 1.0 if date.fromisoformat(rec["due_date"]) >= date.fromisoformat(rec["invoice_date"]) else 0.0
    else:
        checks["due_after_invoice"] = None

    pre, tax, tot = _num(rec.get("pretax_amount")), _num(rec.get("total_tax_amount")), _num(rec.get("total_amount"))
    shipping = _num(rec.get("shipping_charges")) or 0.0
    credits = sum(_num(rec.get(k)) or 0.0 for k in CREDIT_KEYS)  # e.g. insurance payments: total is then the balance due
    if None not in (pre, tax, tot):
        ok = any(_close(pre + tax + s - c, tot, 0.05) for s in (shipping, 0.0) for c in (credits, 0.0))
        checks["totals_reconcile"] = 1.0 if ok else 0.0
    else:
        checks["totals_reconcile"] = None

    items = [i for i in (rec.get("items") or []) if isinstance(i, dict)]
    line_ok = []
    for i in items:  # quantity x unit price, or x net price when a discount applies
        q, t = _num(i.get("quantity")), _num(i.get("total_price"))
        prices = [p for p in (_num(i.get("unit_price")), _num(i.get("net_price"))) if p is not None]
        if q is not None and t is not None and prices:
            line_ok.append(any(_close(q * p, t, 0.02 + 0.005 * max(q, 1.0)) for p in prices))
    checks["line_math"] = sum(line_ok) / len(line_ok) if line_ok else None
    totals = [t for i in items if (t := _num(i.get("total_price"))) is not None]
    checks["items_sum_to_pretax"] = (1.0 if _close(sum(totals), pre, 0.02 + 0.01 * len(totals)) else 0.0) if totals and pre is not None else None
    # format checks for string fields where a wrong value usually breaks the format (they cannot see a subtly wrong digit)
    fmt = [bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(sender["sender_email"]).strip())) for _ in [0] if sender.get("sender_email")]
    fmt += [bool(re.fullmatch(r"[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?", str(sender["sender_bic"]).strip())) for _ in [0] if sender.get("sender_bic")]
    fmt += [bool(re.fullmatch(r"[A-Z]{3}", str(rec["currency"]).strip())) for _ in [0] if rec.get("currency")]
    checks["formats_valid"] = sum(fmt) / len(fmt) if fmt else None
    n = rec.get("total_number_of_items")
    checks["item_count"] = (1.0 if n == len(items) else 0.0) if isinstance(n, int) and items else None
    return checks


def bol_checks(rec: dict[str, Any], spec_path=None) -> dict[str, float | None]:
    spec = json.loads((spec_path or BOL_SPEC).read_text())
    flat = {k: v for blk in rec.values() if isinstance(blk, dict) for k, v in blk.items()} if all(isinstance(v, dict) for v in rec.values()) else rec
    req = pat = req_ok = pat_ok = 0
    for b in spec["blocks"]:
        for f in b.get("fields", []):
            val = flat.get(f["name"])
            if f.get("required"):
                req += 1
                req_ok += val not in (None, "")
            if f.get("pattern") and val not in (None, ""):
                pat += 1
                pat_ok += re.fullmatch(f["pattern"], str(val).strip()) is not None
    return {"required_present": req_ok / req if req else None, "patterns_valid": pat_ok / pat if pat else None}


def quality(family: str, record: dict[str, Any]) -> dict[str, Any]:
    checks = {"invoice": invoice_checks, "bill_of_lading": bol_checks}[family](record)
    vals = [v for v in checks.values() if v is not None]
    return {"score": round(sum(vals) / len(vals), 4) if vals else None, "checks": checks, "n_checks": len(vals)}
