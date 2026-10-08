#!/usr/bin/env python3
"""Download the curated GEHA PDF corpus from its canonical manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


USER_AGENT = "geha-corpus-downloader/1.0 (+local research corpus)"
ALLOWED_HOSTS = {"geha.com", "www.geha.com"}

# These documents were retained separately in the reference corpus because
# their native text layer was not consistent with the source PDF rendering.
PATH_OVERRIDES = {
    "geha-coverage-policy-infertility-services.pdf":
        "coverage-policies/aa_source_not_consistent/geha-coverage-policy-infertility-services.pdf",
    "geha-coverage-policy-intraosseous-radiofrequency-ablation-of-the-basivertebral-nerve.pdf":
        "coverage-policies/aa_source_not_consistent/geha-coverage-policy-intraosseous-radiofrequency-ablation-of-the-basivertebral-nerve.pdf",
    "geha-medical-necessity-review-criteria.pdf":
        "coverage-policies/aa_source_not_consistent/geha-medical-necessity-review-criteria.pdf",
}


@dataclass(frozen=True)
class Result:
    relative_path: str
    url: str
    status: str
    bytes: int
    sha256: str
    expected_sha256: str
    error: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validated_destination(output_dir: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".pdf":
        raise ValueError(f"unsafe PDF path: {relative_path!r}")
    destination = (output_dir / Path(*relative.parts)).resolve()
    destination.relative_to(output_dir.resolve())
    return destination


def normalized_relative_path(document: dict[str, Any]) -> str:
    filename = PurePosixPath(str(document["relative_path"])).name
    return PATH_OVERRIDES.get(filename, str(document["relative_path"]))


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise ValueError(f"URL is not an allowed GEHA HTTPS URL: {url!r}")


def download_one(
    document: dict[str, Any],
    output_dir: Path,
    timeout: float,
    retries: int,
    strict_hash: bool,
) -> Result:
    relative_path = normalized_relative_path(document)
    url = str(document["url"])
    expected = str(document.get("sha256", "")).lower()
    destination = validated_destination(output_dir, relative_path)
    validate_url(url)

    if destination.is_file():
        actual = sha256_file(destination)
        if not expected or actual == expected:
            return Result(relative_path, url, "already_verified", destination.stat().st_size, actual, expected)

    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*;q=0.8"},
            )
            digest = hashlib.sha256()
            total = 0
            prefix = b""
            with urllib.request.urlopen(request, timeout=timeout) as response, part.open("wb") as handle:
                final_host = (urlparse(response.geturl()).hostname or "").lower()
                if final_host not in ALLOWED_HOSTS:
                    raise ValueError(f"redirected to disallowed host: {final_host!r}")
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    if len(prefix) < 5:
                        prefix = (prefix + block)[:5]
                    handle.write(block)
                    digest.update(block)
                    total += len(block)
                handle.flush()
                os.fsync(handle.fileno())

            actual = digest.hexdigest()
            if prefix != b"%PDF-":
                raise ValueError("response is not a PDF")
            if total == 0:
                raise ValueError("empty response")
            if strict_hash and expected and actual != expected:
                raise ValueError(f"SHA-256 mismatch: expected {expected}, received {actual}")

            part.replace(destination)
            status = "downloaded" if not expected or actual == expected else "downloaded_changed"
            return Result(relative_path, url, status, total, actual, expected)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
            part.unlink(missing_ok=True)
            if attempt <= retries:
                time.sleep(min(2 ** (attempt - 1), 8))

    return Result(relative_path, url, "failed", 0, "", expected, str(last_error))


def load_documents(manifest_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("manifest must contain a non-empty 'documents' list")

    seen: set[str] = set()
    for document in documents:
        for key in ("url", "relative_path"):
            if not isinstance(document.get(key), str) or not document[key]:
                raise ValueError(f"manifest document is missing {key!r}")
        relative_path = normalized_relative_path(document)
        if relative_path in seen:
            raise ValueError(f"duplicate output path: {relative_path}")
        seen.add(relative_path)
    return documents


def parse_args() -> argparse.Namespace:
    source_dir = Path(__file__).resolve().parent
    project_dir = source_dir.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=source_dir / "documents.json")
    parser.add_argument("--output-dir", type=Path, default=project_dir / "downloads")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--allow-changed",
        action="store_true",
        help="Keep a valid PDF even if its current SHA-256 differs from the curated manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.retries < 0 or args.timeout <= 0:
        raise SystemExit("workers must be >= 1, retries >= 0, and timeout > 0")

    manifest_path = args.manifest.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    documents = load_documents(manifest_path)

    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                download_one,
                document,
                output_dir,
                args.timeout,
                args.retries,
                not args.allow_changed,
            ): normalized_relative_path(document)
            for document in documents
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            message = f"[{result.status}] {result.relative_path}"
            if result.error:
                message += f": {result.error}"
            print(message, flush=True)

    results.sort(key=lambda item: item.relative_path)
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    summary = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "requested": len(documents),
        "counts": counts,
        "results": [asdict(result) for result in results],
    }
    summary_path = Path(__file__).resolve().parent.parent / "download_run.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    failed = counts.get("failed", 0)
    print(f"Completed {len(results)} documents; failures={failed}; summary={summary_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
