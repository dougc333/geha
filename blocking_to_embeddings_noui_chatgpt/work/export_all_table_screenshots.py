"""Batch bordered-table crops from original GEHA PDFs (no OCR).

Reuses the existing detector. OCR-derived *_openai.pdf files are excluded.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageOps
from render_table_detection_apng import detect


def export(source, destination):
    folder = destination / source.stem
    folder.mkdir(parents=True, exist_ok=True)
    records, pages = [], []
    with pdfplumber.open(source) as pdf, pdfium.PdfDocument(source) as renderer:
        for number, page in enumerate(pdf.pages, 1):
            tables = detect(page)
            method = 'thin-rectangle borders'
            if not tables:
                # Other PDF producers encode borders as actual line objects.
                tables = [t for t in page.find_tables({
                    'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'
                }) if len(t.columns) >= 2 and len(t.rows) >= 2]
                method = 'PDF vector lines (strict)'
            pages.append({'page': number, 'characters': len(page.chars),
                          'tables': len(tables), 'image_count': len(page.images),
                          'review_needed': not page.chars})
            if not tables:
                continue
            raster = renderer[number - 1]
            bitmap = raster.render(scale=3)
            image = bitmap.to_pil().convert('RGB')
            bitmap.close()
            raster.close()
            for index, table in enumerate(sorted(tables, key=lambda t: (t.bbox[1], t.bbox[0])), 1):
                x0, y0, x1, y1 = table.bbox
                sx, sy = image.width / page.width, image.height / page.height
                box = (max(0, math.floor((x0 - 4) * sx)), max(0, math.floor((y0 - 4) * sy)),
                       min(image.width, math.ceil((x1 + 4) * sx)), min(image.height, math.ceil((y1 + 4) * sy)))
                crop = image.crop(box)
                path = folder / f'page-{number:02d}-table-{index:02d}.png'
                crop.save(path, dpi=(216, 216))
                with Image.open(path) as check:
                    check.load()
                    assert check.size == crop.size
                rows = [[re.sub(r'\s+', ' ', c or '').strip() for c in row] for row in table.extract()]
                records.append({'page': number, 'table_on_page': index, 'method': method,
                                'bbox_points': list(table.bbox), 'page_size_points': [page.width, page.height],
                                'rows': rows, 'text_available': any(any(c for c in row) for row in rows),
                                'rows_including_header': len(rows), 'columns': len(table.columns),
                                'screenshot': path.name, 'size_pixels': list(crop.size),
                                'screenshot_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                crop.close()
            image.close()
    manifest = {'source_pdf': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'render_dpi': 216, 'coordinate_system': 'PDF points, top-left origin',
                'limitations': 'Bordered vector tables only; no OCR. No detection does not prove absence of tables.',
                'pages': pages, 'tables': records}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    md = []
    for r in records:
        if not r['text_available']:
            md.append(f'## Page {r["page"]}, table {r["table_on_page"]}\n\nCell text unavailable without OCR. See screenshot: {r["screenshot"]}')
            continue
        lines = ['| ' + ' | '.join(c.replace('|', '\\|') for c in row) + ' |' for row in r['rows']]
        lines.insert(1, '| ' + ' | '.join(['---'] * r['columns']) + ' |')
        md.append(f'## Page {r["page"]}, table {r["table_on_page"]}\n\n' + '\n'.join(lines))
    (folder / 'tables.md').write_text('\n\n'.join(md) + '\n')
    return {'document': source.name, 'folder': str(folder), 'pages': len(pages), 'tables': len(records),
            'status': 'ok' if records else 'no_tables_detected',
            'pages_without_text': [p['page'] for p in pages if p['review_needed']]}, records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(p for p in args.source_dir.glob('*.pdf') if not p.stem.endswith('_openai'))
    summary, previews = [], []
    for source in sources:
        try:
            entry, records = export(source, args.output_dir)
            previews.extend((Path(entry['folder']) / r['screenshot'], source.stem, r) for r in records)
        except Exception as exc:
            entry = {'document': source.name, 'status': 'error', 'error': str(exc), 'tables': 0}
        summary.append(entry)
        print(json.dumps(entry), flush=True)
    report = {'documents': len(sources), 'tables': sum(s['tables'] for s in summary), 'results': summary}
    (args.output_dir / 'batch-summary.json').write_text(json.dumps(report, indent=2) + '\n')
    # Contact sheets allow quick visual review of every exported crop.
    for offset in range(0, len(previews), 12):
        group = previews[offset:offset + 12]
        sheet = Image.new('RGB', (1600, 4 * 280), 'white')
        draw = ImageDraw.Draw(sheet)
        for j, (path, name, record) in enumerate(group):
            x, y = (j % 3) * 533, (j // 3) * 280
            title = name.removeprefix('geha-coverage-policy-').removeprefix('geha-')
            draw.text((x + 8, y + 5), title[:65], fill='black')
            draw.text((x + 8, y + 22), f'Page {record["page"]}, table {record["table_on_page"]}: {record["rows_including_header"]} rows x {record["columns"]} cols', fill='black')
            with Image.open(path) as im:
                thumb = ImageOps.contain(im, (515, 230))
                sheet.paste(thumb, (x + 8, y + 45))
        sheet.save(args.output_dir / f'contact-sheet-{offset // 12 + 1:02d}.png')
    print(json.dumps({'documents': report['documents'], 'tables': report['tables'],
                      'errors': [s for s in summary if s['status'] == 'error']}), flush=True)


if __name__ == '__main__':
    main()
