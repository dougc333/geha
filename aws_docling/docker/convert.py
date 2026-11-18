"""Send one PDF to the local Docling Serve container and save its Markdown."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def multipart(pdf: Path, fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = f"docling-{uuid4().hex}"
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    chunks.append(
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
         f"filename=\"{pdf.name}\"\r\nContent-Type: application/pdf\r\n\r\n").encode()
    )
    chunks.extend((pdf.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode()))
    return b"".join(chunks), boundary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:5011")
    parser.add_argument("--format", choices=("md", "json", "html"), default="md",
                        help="Save Markdown, Docling JSON, or HTML")
    parser.add_argument("--table-mode", choices=("accurate", "fast"), default="accurate")
    parser.add_argument("--no-cell-matching", action="store_true",
                        help="Let the table model define cell text instead of matching PDF text cells")
    parser.add_argument("--no-table-structure", action="store_true")
    parser.add_argument("--chart-extraction", action="store_true",
                        help="Run the chart-data model; slower and may need additional model weights")
    parser.add_argument("--chart-preset", help="For example granite_vision_v4")
    parser.add_argument("--classify-pictures", action="store_true")
    parser.add_argument("--describe-pictures", action="store_true")
    parser.add_argument("--picture-description-preset", help="For example smolvlm")
    parser.add_argument("--image-mode", choices=("embedded", "placeholder"), default="embedded")
    parser.add_argument("--image-scale", type=float, default=2.0)
    parser.add_argument("--page-images", action="store_true")
    parser.add_argument("--no-images", action="store_true")
    args = parser.parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error("pdf must be an existing .pdf file")
    if args.chart_preset and not args.chart_extraction:
        parser.error("--chart-preset requires --chart-extraction")
    if args.picture_description_preset and not args.describe_pictures:
        parser.error("--picture-description-preset requires --describe-pictures")
    if args.image_scale <= 0:
        parser.error("--image-scale must be greater than zero")
    output = args.output or Path(__file__).with_name("output") / f"{args.pdf.stem}.{args.format}"
    fields = {
        "to_formats": args.format,
        "image_export_mode": args.image_mode,
        "include_images": str(not args.no_images).lower(),
        "include_page_images": str(args.page_images).lower(),
        "images_scale": str(args.image_scale),
        "do_table_structure": str(not args.no_table_structure).lower(),
        "table_mode": args.table_mode,
        "table_cell_matching": str(not args.no_cell_matching).lower(),
        "do_chart_extraction": str(args.chart_extraction).lower(),
        "do_picture_classification": str(args.classify_pictures).lower(),
        "do_picture_description": str(args.describe_pictures).lower(),
    }
    if args.chart_preset:
        fields["chart_extraction_preset"] = args.chart_preset
    if args.picture_description_preset:
        fields["picture_description_preset"] = args.picture_description_preset
    body, boundary = multipart(args.pdf, fields)
    request = Request(
        args.url.rstrip("/") + "/v1/convert/file", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "Accept": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=600) as response:
            result = json.load(response)
    except (HTTPError, URLError) as error:
        raise SystemExit(f"Docling server request failed: {error}") from error
    if result.get("status") != "success":
        raise SystemExit(f"Docling conversion failed: {result.get('errors')}")
    content = (result.get("document") or {}).get({
        "md": "md_content", "json": "json_content", "html": "html_content"
    }[args.format])
    if not content:
        raise SystemExit(f"Docling returned no {args.format} content")
    rendered = json.dumps(content, indent=2) + "\n" if args.format == "json" else content
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Saved {output} ({len(rendered.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
