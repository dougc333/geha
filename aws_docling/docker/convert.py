"""Send one PDF to the local Docling Serve container and save its Markdown."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def multipart(pdf: Path) -> tuple[bytes, str]:
    boundary = f"docling-{uuid4().hex}"
    chunks = []
    for name, value in (("to_formats", "md"), ("image_export_mode", "embedded"),
                        ("include_images", "true")):
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
    args = parser.parse_args()
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error("pdf must be an existing .pdf file")
    output = args.output or Path(__file__).with_name("output") / f"{args.pdf.stem}.md"
    body, boundary = multipart(args.pdf)
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
    markdown = (result.get("document") or {}).get("md_content")
    if not markdown:
        raise SystemExit("Docling returned no Markdown")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    print(f"Saved {output} ({len(markdown.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
