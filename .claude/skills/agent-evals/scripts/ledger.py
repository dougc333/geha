"""Append-only experiment ledger for hill-climbing.

  python ledger.py add  LEDGER.jsonl --name NAME --split dev --metric recall=0.91 --metric cost_usd=0.4 \
                        [--note TEXT] [--seed 1] [--budget 5]
  python ledger.py best LEDGER.jsonl --metric recall --split dev [--lower-is-better]
  python ledger.py show LEDGER.jsonl [--split dev]

`add` records one experiment (losing ones too) and, with --budget, warns once the summed
cost_usd of all experiments passes the cap. `best` groups rows by name, averages each
config over its seeds, and prints the spread, so a one-seed win is visible as such.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def parse_metrics(items: list[str]) -> dict[str, float]:
    metrics = {}
    for item in items:
        key, _, value = item.partition("=")
        if not value:
            raise SystemExit(f"--metric expects name=value, got {item!r}")
        metrics[key] = float(value)
    return metrics


def cmd_add(args) -> None:
    row = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "name": args.name,
           "split": args.split, "seed": args.seed, "metrics": parse_metrics(args.metric), "note": args.note}
    with args.ledger.open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"logged {args.name} ({args.split}, seed {args.seed}): {row['metrics']}")
    if args.budget is not None:
        spent = sum(r["metrics"].get("cost_usd", 0.0) for r in load(args.ledger))
        print(f"spent ${spent:.2f} of ${args.budget:.2f}")
        if spent > args.budget:
            print("OVER BUDGET: stop and ask before running more paid experiments")


def grouped(rows: list[dict], metric: str, split: str | None) -> dict[str, list[float]]:
    groups: dict[str, list[float]] = {}
    for r in rows:
        if (split and r["split"] != split) or metric not in r["metrics"]:
            continue
        groups.setdefault(r["name"], []).append(r["metrics"][metric])
    return groups


def cmd_best(args) -> None:
    groups = grouped(load(args.ledger), args.metric, args.split)
    if not groups:
        raise SystemExit(f"no rows with metric {args.metric!r} on split {args.split!r}")
    ranked = sorted(groups.items(), key=lambda kv: statistics.mean(kv[1]), reverse=not args.lower_is_better)
    print(f"{'config':<32}{'mean':>10}{'min':>10}{'max':>10}{'runs':>6}")
    for name, values in ranked:
        print(f"{name:<32}{statistics.mean(values):>10.4f}{min(values):>10.4f}{max(values):>10.4f}{len(values):>6}")
    (top, tv), rest = ranked[0], ranked[1:]
    if rest:
        _, rv = rest[0]
        overlap = (min(tv) <= max(rv)) if not args.lower_is_better else (max(tv) >= min(rv))
        if len(tv) < 2:
            print(f"\n{top} leads on a single run: repeat it with more seeds before keeping it")
        elif overlap:
            print(f"\n{top} leads, but its range overlaps the runner-up's: not a clear win")


def cmd_show(args) -> None:
    for r in load(args.ledger):
        if args.split and r["split"] != args.split:
            continue
        metrics = ", ".join(f"{k}={v:g}" for k, v in r["metrics"].items())
        print(f"{r['time']}  {r['split']:<5} seed={r['seed']}  {r['name']:<28} {metrics}  {r.get('note') or ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add")
    add.add_argument("ledger", type=Path)
    add.add_argument("--name", required=True)
    add.add_argument("--split", default="dev", choices=["dev", "test", "shift"])
    add.add_argument("--metric", action="append", default=[], required=True)
    add.add_argument("--seed", type=int, default=0)
    add.add_argument("--note", default="")
    add.add_argument("--budget", type=float)
    add.set_defaults(func=cmd_add)

    best = sub.add_parser("best")
    best.add_argument("ledger", type=Path)
    best.add_argument("--metric", required=True)
    best.add_argument("--split", default="dev")
    best.add_argument("--lower-is-better", action="store_true")
    best.set_defaults(func=cmd_best)

    show = sub.add_parser("show")
    show.add_argument("ledger", type=Path)
    show.add_argument("--split")
    show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
