"""Serve a local slideshow of PDF-page PNGs and Docling HTML table extracts."""

from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT.parent / "downloads" / "coverage-policies"


def discover_artifacts(
    directory: Path, *, recursive: bool = False, policy: str = "", corrected_only: bool = False
) -> tuple[list[str], list[str]]:
    """Return browser-safe relative URLs for source pages and Docling HTML."""
    directory = directory.expanduser().resolve()
    iterator = directory.rglob if recursive else directory.glob
    policy_key = policy.casefold().strip()

    def matches(path: Path) -> bool:
        return not policy_key or policy_key in path.name.casefold()

    page_images = sorted(
        path for path in iterator("*_images_*.png") if path.is_file() and matches(path)
    )
    docling_html = sorted(
        path
        for path in iterator("*.html")
        if path.is_file()
        and "docling" in path.name.casefold()
        and (not corrected_only or "_corrected" in path.stem.casefold())
        and matches(path)
    )

    def relative_url(path: Path) -> str:
        relative = path.resolve().relative_to(directory).as_posix()
        return "/files/" + quote(relative, safe="/")

    return [relative_url(path) for path in page_images], [
        relative_url(path) for path in docling_html
    ]


def prepare_policy_artifacts(
    directory: Path,
    policy: str,
    *,
    cache_root: Path | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> Path:
    """Create local-only review artifacts when a selected policy has none."""
    directory = directory.expanduser().resolve()
    policy_key = policy.casefold().strip()
    if not policy_key:
        raise ValueError("A policy filter is required to prepare artifacts")
    matches = sorted(
        path
        for path in directory.glob("*.pdf")
        if policy_key in path.name.casefold()
    )
    if not matches:
        raise FileNotFoundError(f"No top-level PDF filename contains {policy!r}")
    if len(matches) > 1:
        names = ", ".join(path.name for path in matches)
        raise ValueError(f"Policy filter {policy!r} matches multiple PDFs: {names}")

    pdf_path = matches[0]
    output_dir = (cache_root or ROOT / "slideshow_cache") / pdf_path.stem
    pages, tables = discover_artifacts(output_dir) if output_dir.is_dir() else ([], [])
    if pages and tables:
        return output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Incomplete slideshow cache: {output_dir}. Inspect or move it, then retry."
        )

    if runner is None:
        from src.batch_review_graph import run_pdf

        runner = run_pdf
    print(f"Preparing local review artifacts for {pdf_path.name} ...", flush=True)
    runner(pdf_path, output_dir, use_vision=False)
    pages, tables = discover_artifacts(output_dir)
    if not pages or not tables:
        raise RuntimeError(
            f"Extraction completed without both page images and Docling HTML: {output_dir}"
        )
    return output_dir


def viewer_html(page_images: list[str], docling_html: list[str], interval: float) -> str:
    """Create the self-contained slideshow interface."""
    interval_ms = max(250, round(interval * 1000))
    pages_json = json.dumps(page_images).replace("</", "<\\/")
    html_json = json.dumps(docling_html).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GEHA extraction review slideshow</title>
  <style>
    :root {{ color-scheme: light; font-family: Inter, system-ui, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef2f6; color: #102a43; }}
    header {{ display: flex; align-items: center; gap: 12px; padding: 12px 18px;
      background: #082f49; color: white; }}
    header h1 {{ margin: 0 auto 0 0; font-size: 18px; }}
    button {{ border: 1px solid #9fb3c8; border-radius: 6px; background: white;
      color: #102a43; padding: 7px 12px; cursor: pointer; }}
    button:hover {{ background: #e6f0f7; }}
    main {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px;
      height: calc(100vh - 58px); padding: 14px; }}
    section {{ min-width: 0; display: grid; grid-template-rows: auto 1fr;
      background: white; border: 1px solid #bcccdc; border-radius: 8px; overflow: hidden; }}
    .panel-title {{ display: flex; justify-content: space-between; gap: 12px;
      padding: 9px 12px; border-bottom: 1px solid #d9e2ec; font-size: 14px; }}
    .name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #486581; }}
    .stage {{ min-height: 0; display: grid; place-items: center; overflow: auto; background: #f8fafc; }}
    img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
    iframe {{ width: 100%; height: 100%; border: 0; background: white; }}
    .empty {{ padding: 24px; text-align: center; color: #627d98; }}
    @media (max-width: 900px) {{
      main {{ grid-template-columns: 1fr; height: auto; }}
      section {{ min-height: 70vh; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>PDF source ↔ Docling HTML review</h1>
    <button id="previous" type="button">Previous</button>
    <button id="toggle" type="button">Pause</button>
    <button id="next" type="button">Next</button>
  </header>
  <main>
    <section>
      <div class="panel-title"><strong>Source PDF page</strong><span id="page-name" class="name"></span></div>
      <div id="page-stage" class="stage"></div>
    </section>
    <section>
      <div class="panel-title"><strong>Docling HTML table</strong><span id="html-name" class="name"></span></div>
      <div id="html-stage" class="stage"></div>
    </section>
  </main>
  <script>
    const pageImages = {pages_json};
    const doclingHtml = {html_json};
    const intervalMs = {interval_ms};
    let index = 0;
    let playing = true;
    let timer;

    const label = (url, current, total) => total
      ? `${{current + 1}}/${{total}} · ${{decodeURIComponent(url.split('/').pop())}}`
      : 'No matching files';

    function render() {{
      const pageStage = document.getElementById('page-stage');
      const htmlStage = document.getElementById('html-stage');
      const pageIndex = pageImages.length ? index % pageImages.length : 0;
      const htmlIndex = doclingHtml.length ? index % doclingHtml.length : 0;
      pageStage.replaceChildren();
      htmlStage.replaceChildren();

      if (pageImages.length) {{
        const image = document.createElement('img');
        image.src = pageImages[pageIndex];
        image.alt = 'Rendered source PDF page';
        pageStage.append(image);
      }} else {{
        pageStage.innerHTML = '<div class="empty">No <code>*_images_*.png</code> files found.</div>';
      }}

      if (doclingHtml.length) {{
        const frame = document.createElement('iframe');
        frame.src = doclingHtml[htmlIndex];
        frame.title = 'Rendered Docling HTML table';
        htmlStage.append(frame);
      }} else {{
        htmlStage.innerHTML = '<div class="empty">No Docling HTML files found.</div>';
      }}

      document.getElementById('page-name').textContent = label(
        pageImages[pageIndex] || '', pageIndex, pageImages.length);
      document.getElementById('html-name').textContent = label(
        doclingHtml[htmlIndex] || '', htmlIndex, doclingHtml.length);
    }}

    function schedule() {{
      clearInterval(timer);
      if (playing) timer = setInterval(() => {{ index += 1; render(); }}, intervalMs);
    }}

    document.getElementById('previous').onclick = () => {{ index = Math.max(0, index - 1); render(); schedule(); }};
    document.getElementById('next').onclick = () => {{ index += 1; render(); schedule(); }};
    document.getElementById('toggle').onclick = event => {{
      playing = !playing;
      event.currentTarget.textContent = playing ? 'Pause' : 'Play';
      schedule();
    }};
    document.addEventListener('keydown', event => {{
      if (event.key === 'ArrowLeft') document.getElementById('previous').click();
      if (event.key === 'ArrowRight') document.getElementById('next').click();
      if (event.key === ' ') {{ event.preventDefault(); document.getElementById('toggle').click(); }}
    }});
    render();
    schedule();
  </script>
</body>
</html>
"""


class SlideshowHandler(SimpleHTTPRequestHandler):
    """Serve the generated viewer and restrict artifacts to the selected root."""

    viewer: bytes = b""

    def do_GET(self) -> None:  # noqa: N802 - required HTTP handler name
        if self.path.split("?", 1)[0] in {"/", "/index.html"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.viewer)))
            self.end_headers()
            self.wfile.write(self.viewer)
            return
        if self.path.startswith("/files/"):
            self.path = self.path[len("/files") :]
            return super().do_GET()
        self.send_error(404)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=PDF_DIR,
                        help="Source PDF directory (default: downloads/coverage-policies)")
    parser.add_argument("--policy", default="", help="Only files whose names contain this text")
    parser.add_argument("--recursive", action="store_true", help="Include review_runs subdirectories")
    parser.add_argument("--corrected-only", action="store_true", help="Show only *_corrected.html artifacts")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds per artifact")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")

    directory = args.directory.expanduser().resolve()
    if not directory.is_dir():
        parser.error(f"Not a directory: {directory}")
    artifact_directory = ROOT if directory == PDF_DIR.resolve() else directory
    pages, tables = discover_artifacts(
        artifact_directory, recursive=args.recursive, policy=args.policy,
        corrected_only=args.corrected_only
    )
    if args.policy and (not pages or not tables):
        artifact_directory = prepare_policy_artifacts(directory, args.policy)
        pages, tables = discover_artifacts(artifact_directory, corrected_only=args.corrected_only)
    SlideshowHandler.viewer = viewer_html(pages, tables, args.interval).encode("utf-8")
    handler = partial(SlideshowHandler, directory=str(artifact_directory))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {len(pages)} PDF pages and {len(tables)} Docling HTML files")
    print(f"Open http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
