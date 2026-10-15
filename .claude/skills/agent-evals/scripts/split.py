"""Split a JSONL eval file into dev and test by a hash of each case's id.

The same id always lands in the same split, so adding cases later never moves
existing ones between dev and test.

  python split.py cases.jsonl --id-field id --test-frac 0.3 [--salt v1]

Writes cases.dev.jsonl and cases.test.jsonl next to the input and prints counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def in_test(case_id: str, frac: float, salt: str) -> bool:
    digest = hashlib.sha256(f"{salt}:{case_id}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF < frac


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--test-frac", type=float, default=0.3)
    parser.add_argument("--salt", default="v1", help="change only to deliberately draw a fresh test split")
    args = parser.parse_args()

    dev, test = [], []
    for n, line in enumerate(args.path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if args.id_field not in case:
            raise SystemExit(f"line {n}: no {args.id_field!r} field")
        (test if in_test(str(case[args.id_field]), args.test_frac, args.salt) else dev).append(line)

    stem = args.path.with_suffix("")
    for name, rows in (("dev", dev), ("test", test)):
        out = Path(f"{stem}.{name}.jsonl")
        out.write_text("\n".join(rows) + ("\n" if rows else ""))
        print(f"{name}: {len(rows):>5}  -> {out}")
    if len(test) < 30:
        print(f"note: only {len(test)} test cases; differences of a case or two are noise")


if __name__ == "__main__":
    main()
