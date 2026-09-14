"""Evaluate the vector resolver against ground truth at several thresholds."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

import build_vector_db as vdb

HERE = Path(__file__).parent
gt = json.loads((HERE / "claim_forms_garbled" / "ground_truth.json").read_text())

FIELDS = ["diagnosis", "cpt", "pos", "dos", "charge", "npi"]
r = vdb.VectorResolver()


def evaluate(thresh):
    correct = 0
    total = 0
    flagged_missing_correctly = 0
    wrong = 0
    missing_total = 0
    rows = []
    for c in gt:
        ocr = (HERE / "ocr_output" / f"{c['claim_id']}.ocrtext").read_text()
        res = vdb.resolve_all(r, ocr, thresh=thresh)
        # ground truth "expected" fields: those NOT deliberately blanked
        row = {}
        for f in FIELDS:
            expected = str(c[f]) if c[f] not in ("", None) else None
            got = res.get(f)
            if expected is None:
                missing_total += 1
                if got is None:
                    flagged_missing_correctly += 1
            else:
                total += 1
                if got == expected:
                    correct += 1
                else:
                    wrong += 1
            row[f] = (expected, got)
        rows.append((c["claim_id"], row))
    acc = correct / total if total else 0
    return {
        "thresh": thresh,
        "correct": correct,
        "total": total,
        "acc": round(acc, 3),
        "wrong": wrong,
        "missing_correct": flagged_missing_correctly,
        "missing_total": missing_total,
    }


for th in [0.60, 0.65, 0.70, 0.74, 0.78, 0.82]:
    print(evaluate(th))

print("\n--- detail @0.74 ---")
r = vdb.VectorResolver()
for c in gt:
    ocr = (HERE / "ocr_output" / f"{c['claim_id']}.ocrtext").read_text()
    res = vdb.resolve_all(r, ocr, thresh=0.74)
    print(c["claim_id"], {f: (str(c[f]) if c[f] else None, res.get(f)) for f in FIELDS})
