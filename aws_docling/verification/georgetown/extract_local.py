"""Reproduce the Georgetown figure extraction without launching an AWS task."""

import argparse
import json
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import ImageRefMode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    parser.add_argument("--chart-extraction", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    options = PdfPipelineOptions(
        generate_page_images=True,
        generate_picture_images=True,
        do_chart_extraction=args.chart_extraction,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(str(args.pdf))
    if result.status.value != "success":
        raise RuntimeError(f"Docling conversion status: {result.status}")

    markdown = result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
    (args.output / "document-with-images.md").write_text(markdown, encoding="utf-8")
    figures = []
    for index, picture in enumerate(result.document.pictures, 1):
        image = picture.get_image(result.document)
        if image is None:
            continue
        name = f"figure-{index:03}.png"
        image.save(args.output / name)
        figures.append({
            "index": index,
            "file": name,
            "page": picture.prov[0].page_no if picture.prov else None,
            "bbox": list(picture.prov[0].bbox.as_tuple()) if picture.prov else None,
        })
    (args.output / "figures.json").write_text(
        json.dumps({"figures": figures}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Extracted {len(figures)} figures into {args.output}")


if __name__ == "__main__":
    main()
