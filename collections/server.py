"""Small collection reconciliation API for the GEHA inventory UI."""
from __future__ import annotations

import hashlib
import html.parser
import json
import re
import ssl
import urllib.parse
import urllib.request
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # Keep the API usable with the legacy HTML crawler.
    PlaywrightTimeoutError = TimeoutError
    sync_playwright = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from crawl_dir.src.download_geha_docs import download_one
except ImportError:
    download_one = None

CRAWL_DIR = ROOT / "crawl_dir"
MANIFEST = CRAWL_DIR / "src" / "documents.json"
RAW = CRAWL_DIR / "raw"
SNAPSHOT_FILE = Path(__file__).resolve().parent / "inventory-snapshot.json"
PORT = 8520
GEHA_ROOT = "https://www.geha.com/en/resource-center/forms-and-documents"
ALLOWED_HOSTS = {"www.geha.com", "geha.com", "www.mygeha.com", "mygeha.com"}


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"a", "iframe", "link"}:
            href = dict(attrs).get("href") or dict(attrs).get("src")
            if href:
                self.links.append(href)


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "geha-collection-inventory/0.1"})
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=20, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def is_pdf(url: str) -> bool:
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(".pdf") or ".pdf?" in url.lower()


def discover(root_url: str = GEHA_ROOT, max_depth: int = 1) -> list[str]:
    """Discover rendered PDF links, falling back to the static crawler if needed."""
    if sync_playwright is not None:
        return discover_browser(root_url)

    return discover_static(root_url, max_depth)


def discover_browser(root_url: str = GEHA_ROOT) -> list[str]:
    """Use Chromium so JavaScript-rendered GEHA catalog links are included."""
    pdfs: set[str] = set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="geha-collection-inventory/0.2 (browser crawler)",
            viewport={"width": 1440, "height": 1200},
        )
        try:
            try:
                page.goto(root_url, wait_until="domcontentloaded", timeout=20_000)
            except Exception:
                # A slow/blocked page may still have a usable partial DOM.
                pass
            # GEHA keeps analytics connections open, so network-idle may never
            # occur. A short post-load wait is enough for the catalog DOM.
            page.wait_for_timeout(4_000)
            # Trigger lazy-loaded catalog sections before reading the DOM.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)
            hrefs = page.locator("a[href], [data-href], [data-url]").evaluate_all(
                """els => els.flatMap(el => [
                    el.href,
                    el.getAttribute('href'),
                    el.getAttribute('data-href'),
                    el.getAttribute('data-url')
                ]).filter(Boolean)"""
            )
            for href in hrefs:
                url = urllib.parse.urldefrag(urllib.parse.urljoin(root_url, href)).url
                parsed = urllib.parse.urlparse(url)
                if parsed.hostname in ALLOWED_HOSTS and is_pdf(url):
                    pdfs.add(url)
        except Exception:
            return discover_static(root_url)
        finally:
            browser.close()
    return sorted(pdfs)


def discover_static(root_url: str = GEHA_ROOT, max_depth: int = 1) -> list[str]:
    """Legacy HTML-only discovery used when Playwright is unavailable."""
    queue = [(root_url, 0)]
    seen: set[str] = set()
    pdfs: set[str] = set()
    while queue:
        page, depth = queue.pop(0)
        page = urllib.parse.urldefrag(page).url
        if page in seen or urllib.parse.urlparse(page).hostname not in ALLOWED_HOSTS:
            continue
        seen.add(page)
        try:
            links = LinkParser()
            links.feed(fetch(page))
        except Exception:
            continue
        for href in links.links:
            url = urllib.parse.urljoin(page, href)
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname not in ALLOWED_HOSTS:
                continue
            url = urllib.parse.urldefrag(url).url
            if is_pdf(url):
                pdfs.add(url)
            elif depth < max_depth and parsed.path.startswith("/resource-center/"):
                queue.append((url, depth + 1))
    return sorted(pdfs)


def load_manifest() -> list[dict]:
    if not MANIFEST.exists():
        return []
    return json.loads(MANIFEST.read_text(encoding="utf-8")).get("documents", [])


def local_for_url(url: str, manifest: list[dict]) -> tuple[str | None, bool | None]:
    match = next((item for item in manifest if item.get("url") == url), None)
    if match:
        path = RAW / match.get("relative_path", "")
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return match.get("relative_path"), digest == match.get("sha256")
        return match.get("relative_path"), None
    basename = Path(urllib.parse.urlparse(url).path).name
    candidates = list(RAW.rglob(basename)) if basename else []
    return (str(candidates[0].relative_to(CRAWL_DIR)) if candidates else None), None


def processing_state(relative_path: str | None) -> tuple[str, str, bool, str | None]:
    """Return processing, QC, promotion, and note without exposing hashes."""
    if not relative_path:
        return "discovered", "discovered", False, None
    source = f"raw/{relative_path}"
    candidates = []
    for manifest_path in (CRAWL_DIR / "runs").rglob("run-manifest.json"):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("source") == source:
            candidates.append((str(data.get("created_at", "")), manifest_path.parent, data))
    if not candidates:
        return "downloaded", "downloaded", False, None
    _, run_dir, manifest = sorted(candidates)[-1]
    promoted = manifest.get("promotion_status") == "promoted"
    qc_status = "processing"
    qc_path = run_dir / str(manifest.get("qc_report", "qc-report.json"))
    if qc_path.exists():
        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8"))
            qc_status = qc.get("status", "processing")
        except (OSError, json.JSONDecodeError):
            pass
    candidate_md = run_dir / str(manifest.get("candidate", "candidate")) / "document.md"
    processing = "extracted" if candidate_md.exists() and candidate_md.stat().st_size else "processing"
    if promoted:
        qc_status = "promoted"
    elif qc_status not in {"failed", "needs_visual_review"}:
        qc_status = "extracted" if processing == "extracted" else "processing"
    note = f"Latest run: {manifest.get('run_id', run_dir.name)}"
    return processing, qc_status, promoted, note


def crawl_snapshot() -> dict:
    urls = discover()
    manifest = load_manifest()
    now = datetime.now(timezone.utc).isoformat()
    assets = []
    for url in urls:
        raw_path, hash_matches = local_for_url(url, manifest)
        manifest_item = next((item for item in manifest if item.get("url") == url), None)
        processing, qc, promoted, run_note = processing_state(raw_path)
        status = "hash_mismatch" if hash_matches is False else "missing_from_manifest" if not manifest_item else "downloaded" if raw_path else "manifested"
        assets.append({
            "id": hashlib.sha1(url.encode()).hexdigest()[:12],
            "title": (manifest_item or {}).get("title") or Path(urllib.parse.urlparse(url).path).stem.replace("-", " ").title(),
            "summary": (manifest_item or {}).get("description") or "PDF asset discovered from the GEHA forms and documents catalog.",
            "collection": (manifest_item or {}).get("category", "geha-forms-documents"),
            "family": (manifest_item or {}).get("category", "forms"),
            "year": int(re.search(r"20\d{2}", url).group()) if re.search(r"20\d{2}", url) else 0,
            "url": url,
            "rawPath": raw_path,
            "status": status,
            "processing": processing,
            "qc": qc,
            "promoted": promoted,
            "hashMatches": hash_matches,
            "updated": now[:10],
            "pages": None,
            "note": run_note or "Live snapshot; no processing run found.",
        })
    return {"rootUrl": GEHA_ROOT, "createdAt": now, "assets": assets, "discovered": len(assets)}


def save_snapshot(payload: dict) -> dict:
    temporary = SNAPSHOT_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(SNAPSHOT_FILE)
    return payload


def snapshot(force: bool = False) -> dict:
    if not force and SNAPSHOT_FILE.is_file():
        try:
            payload = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
            if isinstance(payload.get("assets"), list):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    return save_snapshot(crawl_snapshot())


def discovered_relative_path(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    marker = "/documents-files/"
    if marker in path:
        relative = path.split(marker, 1)[1]
        filename = Path(relative).name
        if filename in {
            "2025-geha-dental-plan-brochure.pdf",
            "2027-geha-dental-plan-brochure.pdf",
        }:
            return f"dental/fedvip/{filename}"
        return relative
    return f"forms/{Path(path).name}"


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._json({
                "service": "GEHA collection API",
                "ui": "http://127.0.0.1:5178/",
                "endpoints": ["/api/health", "/api/collection-inventory", "POST /api/crawl-snapshot"],
            })
        elif self.path == "/api/health":
            self._json({"ready": True, "rootUrl": GEHA_ROOT})
        elif self.path == "/api/collection-inventory":
            self._json(snapshot(force=False))
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/crawl-snapshot":
            self._json(snapshot(force=True))
        elif self.path == "/api/download-discovered":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            url = str(payload.get("url", ""))
            if not url or not is_pdf(url):
                self._json({"error": "A PDF URL is required"}, 400)
                return
            if download_one is None:
                self._json({"error": "The crawl_dir document downloader is unavailable"}, 500)
                return
            entry = {"url": url, "relative_path": discovered_relative_path(url), "sha256": ""}
            result = download_one(entry, RAW, timeout=60, retries=3, strict_hash=False)
            self._json({**result.__dict__, "destination": str(RAW / result.relative_path)}, 200 if result.status != "failed" else 502)
        else:
            self._json({"error": "Not found"}, 404)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    print(f"GEHA collection API listening on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
