"""CLI for promoting a completely verified run."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline.promotion import promote_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--reviewed-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reviewed",
    )
    args = parser.parse_args()
    print(promote_run(args.run_dir, args.reviewed_root))


if __name__ == "__main__":
    main()

