#!/usr/bin/env python3
"""Add arXiv papers to the chatbot's index from the command line.

    python add_arxiv.py 2305.14314 https://arxiv.org/abs/2310.11511

Each paper is downloaded by the deployed /api/arxiv endpoint into the raw S3
bucket; the chunker -> embedder pipeline indexes it in about 10 seconds. The
endpoint URL comes from --url, $CHATBOT_URL, or the sam-app stack's QueryUrl
output (needs the AWS CLI).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def stack_url(stack: str, region: str) -> str:
    return subprocess.run(
        ["aws", "cloudformation", "describe-stacks", "--stack-name", stack, "--region", region,
         "--query", "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue", "--output", "text"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def call(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{url}: {json.load(exc).get('detail', exc.reason)}") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("papers", nargs="+", help="arXiv IDs or arxiv.org links")
    parser.add_argument("--url", default=os.getenv("CHATBOT_URL"), help="query API base URL")
    parser.add_argument("--stack", default="sam-app")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--no-wait", action="store_true", help="don't wait for indexing")
    args = parser.parse_args()
    base = (args.url or stack_url(args.stack, args.region)).rstrip("/")

    pending = []
    for paper in args.papers:
        result = call(f"{base}/api/arxiv", {"paper": paper})
        print(f"{result['arxiv_id']}: {result['status']} - {result['title']}")
        if result["status"] == "queued":
            pending.append(result["title"])
        time.sleep(3)  # arXiv asks API clients to space out requests

    deadline = time.time() + 120
    while pending and not args.no_wait and time.time() < deadline:
        time.sleep(5)
        indexed = {d["title"] for d in call(f"{base}/api/documents")["documents"] if d["chunks"]}
        for title in [t for t in pending if t in indexed]:
            print(f"indexed: {title}")
            pending.remove(title)
    if pending and not args.no_wait:
        sys.exit(f"still indexing after 2 minutes: {pending} (check the Embedder logs)")


if __name__ == "__main__":
    main()
