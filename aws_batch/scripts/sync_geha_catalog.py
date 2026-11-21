"""Inventory the public GEHA forms catalog and download PDFs missing from raw/.

Existing files are checked across every raw subdirectory before any download.
The catalog and results are saved independently of the demo application.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

PAGE = "https://www.geha.com/en/resource-center/forms-and-documents"
HOSTS = {"www.geha.com", "geha.com", "www.mygeha.com", "mygeha.com"}


def catalog(session: requests.Session) -> list[dict]:
    response = session.get(PAGE, timeout=40)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    script = next((tag.string or tag.text for tag in soup.find_all("script")
                   if "var initialItems" in (tag.string or tag.text or "")), None)
    if script is None:
        raise ValueError("GEHA catalog data was not found")
    match = re.search(r"var initialItems = '(.*?)';", script, re.S)
    if match is None:
        raise ValueError("GEHA catalog format changed")
    items = json.loads(match.group(1))
    records = []
    seen = set()
    for item in items:
        url = urljoin(PAGE, item.get("LinkToResource", ""))
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS or not parsed.path.lower().endswith(".pdf"):
            continue
        if url in seen:
            continue
        seen.add(url)
        records.append({"title": item.get("Title", ""), "url": url,
                        "filename": Path(parsed.path).name, "type": item.get("Type", ""),
                        "last_updated": item.get("LastUpdated", "")})
    return records


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def existing_index(root: Path) -> tuple[dict[str, list[Path]], dict[str, Path]]:
    names: dict[str, list[Path]] = {}
    hashes: dict[str, Path] = {}
    for path in sorted(root.rglob("*.pdf")):
        if not path.is_file():
            continue
        names.setdefault(path.name.casefold(), []).append(path)
        hashes[sha256(path)] = path
    return names, hashes


def download(record: dict, session: requests.Session, root: Path, hashes: dict[str, Path]) -> dict:
    target = root / "geha_misc" / record["filename"]
    try:
        with session.get(record["url"], timeout=90, stream=True) as response:
            response.raise_for_status()
            host = urlsplit(response.url).hostname
            if host not in HOSTS:
                raise ValueError(f"Redirected to unexpected host {host}")
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".geha-", delete=False) as handle:
                temporary = Path(handle.name)
                for block in response.iter_content(1024 * 1024):
                    if block:
                        handle.write(block)
        if temporary.read_bytes()[:5] != b"%PDF-":
            raise ValueError("Response is not a PDF")
        digest = sha256(temporary)
        if digest in hashes:
            temporary.unlink()
            return {**record, "status": "duplicate_content", "existing_path": str(hashes[digest]), "sha256": digest}
        temporary.replace(target)
        return {**record, "status": "downloaded", "path": str(target), "bytes": target.stat().st_size, "sha256": digest}
    except Exception as exc:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        return {**record, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def sync(raw_root: Path, manifest: Path, *, execute: bool = False, workers: int = 4) -> dict:
    if workers < 1 or workers > 8:
        raise ValueError("workers must be in 1..8")
    raw_root.mkdir(parents=True, exist_ok=True)
    (raw_root / "geha_misc").mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; GEHA-public-document-inventory/1.0)",
                            "Accept": "application/pdf,text/html,*/*"})
    records = catalog(session)
    names, hashes = existing_index(raw_root)
    results = []
    missing = []
    for record in records:
        existing = names.get(record["filename"].casefold())
        if existing:
            results.append({**record, "status": "existing_filename", "existing_path": str(existing[0]),
                            "sha256": sha256(existing[0])})
        else:
            missing.append(record)
    if execute:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(download, record, session, raw_root, hashes) for record in missing]
            for future in as_completed(futures):
                results.append(future.result())
    else:
        results.extend({**record, "status": "missing"} for record in missing)
    results.sort(key=lambda x: x["filename"].casefold())
    counts = {state: sum(r["status"] == state for r in results) for state in sorted({r["status"] for r in results})}
    output = {"source": PAGE, "checked_at": datetime.now(timezone.utc).isoformat(),
              "raw_root": str(raw_root), "catalog_count": len(records), "counts": counts, "documents": results}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    result = sync(args.raw_root.resolve(), args.manifest.resolve(), execute=args.execute, workers=args.workers)
    print(json.dumps({"catalog_count": result["catalog_count"], "counts": result["counts"],
                      "manifest": str(args.manifest)}, indent=2))


if __name__ == "__main__":
    main()
