"""Enforce the MCP promotion standard: every tool must qualify for its declared tier.

    python check_promotion.py            # exit 1 if any tool is above the tier it qualifies for
    python check_promotion.py --report   # also show what each tool needs for the next tier

Run in CI: a pull request that raises a tool's tier without meeting the criteria fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from registry import TIERS, requirements
from tools import SPECS

TESTS_DIR = Path(__file__).resolve().parents[1] / "tests"


def existing_tests() -> set[str]:
    names: set[str] = set()
    for path in TESTS_DIR.glob("test_*.py"):
        names.update(re.findall(r"def (test_\w+)\(", path.read_text(encoding="utf-8")))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", action="store_true", help="show what each tool needs for the next tier")
    args = parser.parse_args()
    tests, failures = existing_tests(), 0
    print(f"{'tool':26} {'tier':11} {'data':9} {'access':7} status")
    for spec in SPECS:
        unmet = requirements(spec, spec.tier, tests)
        failures += bool(unmet)
        print(f"{spec.name:26} {spec.tier:11} {spec.data_class:9} {spec.access:7} "
              + ("OK" if not unmet else "FAILS: " + "; ".join(unmet)))
        level = TIERS.index(spec.tier)
        if args.report and not unmet and level + 1 < len(TIERS):
            nxt = TIERS[level + 1]
            blockers = requirements(spec, nxt, tests)
            print(f"{'':26} -> {nxt}: " + ("eligible" if not blockers else "needs " + "; ".join(blockers)))
    print(f"\n{len(SPECS) - failures}/{len(SPECS)} tools meet the standard for their declared tier.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
