"""Per-field accuracy breakdown."""

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_vector_db as vdb

HERE = Path(__file__).parent
gt = json.loads((HERE / "claim_forms_garbled" / "ground_truth.json").read_text())
FIELDS = [
    "diagnosis",
    "cpt",
    "pos",
    "dos",
    "charge",
    "npi",
    "provider",
    "facility",
    "member_id",
    "patient_name",
]
r = vdb.VectorResolver()

per_field = {
    f: {
        "correct": 0,
        "present": 0,
        "wrong": 0,
        "unrecovered": 0,
        "filled_but_missing": 0,
    }
    for f in FIELDS
}
for c in gt:
    ocr = (HERE / "ocr_output" / f"{c['claim_id']}.ocrtext").read_text()
    res = vdb.resolve_all(r, ocr, thresh=0.72)
    for f in FIELDS:
        exp = str(c[f]) if c[f] not in ("", None) else None
        got = res.get(f)
        if exp is None:
            if got is not None:
                per_field[f]["filled_but_missing"] += 1
        else:
            per_field[f]["present"] += 1
            if got == exp:
                per_field[f]["correct"] += 1
            elif got is None:
                per_field[f]["unrecovered"] += 1  # correctly -> NULL -> missing data
            else:
                per_field[f]["wrong"] += 1

print(
    f"{'field':14} {'correct':>8} {'unrecover':>10} {'wrong':>6} {'recover_acc':>12} {'miss_ok':>8}"
)
for f in FIELDS:
    d = per_field[f]
    rec = d["correct"] + d["unrecovered"] + d["wrong"]
    acc = d["correct"] / d["present"] if d["present"] else float("nan")
    rec_acc = d["correct"] / rec if rec else float("nan")
    print(
        f"{f:14} {d['correct']:>4}/{d['present']:<3} {d['unrecovered']:>10} "
        f"{d['wrong']:>6} {rec_acc:>11.0%} {d['filled_but_missing']:>8}"
    )
# aggregate
tot_c = sum(d["correct"] for d in per_field.values())
tot_p = sum(d["present"] for d in per_field.values())
tot_w = sum(d["wrong"] for d in per_field.values())
tot_u = sum(d["unrecovered"] for d in per_field.values())
print(
    f"\nTOTAL  correct={tot_c}/{tot_p}  unrecovered={tot_u} (->missing)  truly_wrong={tot_w}"
)
print(
    f"  overall recovery accuracy: {tot_c / tot_p:.0%}; +unrecovered-as-missing keeps {tot_u} fields honest"
)


# show raw OCR tokens vs truth for the hard fields
print("\n=== raw OCR tokens (all) vs truth for hard fields ===")
for c in gt[:4]:
    ocr = (HERE / "ocr_output" / f"{c['claim_id']}.ocrtext").read_text()
    toks = [t for t in ocr.split() if any(ch.isalnum() for ch in t)][:40]
    print(
        c["claim_id"],
        "diag_truth=",
        repr(c["diagnosis"]),
        "cpt_truth=",
        repr(c["cpt"]),
        "charge_truth=",
        repr(c["charge"]),
    )
    print("   tokens:", toks)
