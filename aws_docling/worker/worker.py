"""One PDF per ECS task; the process exits after conversion."""

import os
import json
import tempfile
from io import BytesIO
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from urllib.request import Request, urlopen
from zipfile import ZIP_DEFLATED, ZipFile

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode


def _heartbeat(stop: Event, stage: list[str], started: float) -> None:
    while not stop.wait(15):
        elapsed = int(monotonic() - started)
        print(f"heartbeat stage={stage[0]} elapsed={elapsed}s", flush=True)


def main() -> None:
    stop = Event()
    stage = ["downloading"]
    started = monotonic()
    print("worker started", flush=True)
    monitor = Thread(target=_heartbeat, args=(stop, stage, started), daemon=True)
    monitor.start()
    try:
        _convert(stage)
        print(f"worker completed in {int(monotonic() - started)}s", flush=True)
    finally:
        stop.set()
        monitor.join(timeout=1)


def _convert(stage: list[str]) -> None:
    cached_before = _cached_models()
    with tempfile.TemporaryDirectory() as directory:
        pdf = Path(directory) / "source.pdf"
        with urlopen(os.environ["SOURCE_URL"], timeout=120) as response:
            pdf.write_bytes(response.read())

        stage[0] = "converting"
        print("conversion started", flush=True)
        options = PdfPipelineOptions(generate_page_images=True, generate_picture_images=True)
        if os.getenv("DO_CHART_EXTRACTION", "false").lower() == "true":
            options.do_chart_extraction = True
        result = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        ).convert(str(pdf))
        if result.status.value != "success":
            raise RuntimeError(f"Docling conversion status: {result.status}")
        markdown = result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
        if not markdown.strip():
            raise RuntimeError("Docling returned empty Markdown")

        stage[0] = "uploading"
        print(f"uploading Markdown ({len(markdown.encode('utf-8'))} bytes)", flush=True)
        _upload(os.environ["OUTPUT_URL"], markdown.encode("utf-8"), "text/markdown; charset=utf-8")
        if os.getenv("FIGURES_URL"):
            figures = _figure_archive(result.document)
            _upload(os.environ["FIGURES_URL"], figures, "application/zip")
            print(f"uploaded figure archive ({len(figures)} bytes)", flush=True)
        if os.getenv("MODELS_URL"):
            inventory = _model_inventory(options, len(result.document.pictures), cached_before)
            _upload(os.environ["MODELS_URL"], json.dumps(inventory, indent=2).encode(), "application/json")
            print(f"uploaded model inventory ({len(inventory['downloaded_models'])} new model directories)", flush=True)


def _upload(url: str, data: bytes, content_type: str) -> None:
    request = Request(url, data=data, headers={"Content-Type": content_type}, method="PUT")
    with urlopen(request, timeout=120):
        pass


def _figure_archive(document) -> bytes:
    buffer = BytesIO()
    manifest = []
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for index, picture in enumerate(document.pictures, 1):
            image = picture.get_image(document)
            if image is None:
                continue
            name = f"figure-{index:03}.png"
            image_bytes = BytesIO()
            image.save(image_bytes, format="PNG")
            archive.writestr(name, image_bytes.getvalue())
            manifest.append({
                "index": index,
                "file": name,
                "page": picture.prov[0].page_no if picture.prov else None,
                "bbox": list(picture.prov[0].bbox.as_tuple()) if picture.prov else None,
            })
        archive.writestr("manifest.json", json.dumps({"figures": manifest}, indent=2))
    print(f"extracted {len(manifest)} figure images", flush=True)
    return buffer.getvalue()


def _cache_root() -> Path:
    return Path(os.getenv("HF_HUB_CACHE") or Path(os.getenv("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub")


def _cached_models() -> list[dict[str, str]]:
    cache = _cache_root()
    return [
        {"name": path.name.removeprefix("models--").replace("--", "/"), "cache_path": str(path)}
        for path in sorted(cache.glob("models--*"))
        if path.is_dir()
    ]


def _model_inventory(options: PdfPipelineOptions, figure_count: int, cached_before: list[dict[str, str]]) -> dict:
    cache = _cache_root()
    models = _cached_models()
    before_names = {model["name"] for model in cached_before}
    return {
        "cache_root": str(cache),
        "cached_models": models,
        "downloaded_models": [model for model in models if model["name"] not in before_names],
        "pipeline": {
            "table_structure": options.do_table_structure,
            "chart_extraction": getattr(options, "do_chart_extraction", False),
            "picture_images": options.generate_picture_images,
        },
        "figures": figure_count,
    }


if __name__ == "__main__":
    main()
