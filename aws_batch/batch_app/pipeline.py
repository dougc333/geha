"""Evidence-first batch extraction for arbitrary public PDFs.

Crops preserve the PDF pixels. A crop spec is explicitly not an authored chart
spec; the latter requires value/geometry verification before publication.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from bounding_box.figure_bbox_app.source_evidence_specs import assemble_source_evidence_specs


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_slug(value: str) -> str:
    return re.sub(r'[^a-z0-9-]+', '-', value.casefold()).strip('-')[:70] or 'document'


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def figure_regions(page: pymupdf.Page) -> list[tuple[str, pymupdf.Rect]]:
    area = page.rect.get_area()
    candidates: list[tuple[str, pymupdf.Rect]] = []
    for info in page.get_image_info():
        rect = pymupdf.Rect(info['bbox']) & page.rect
        if area * .025 <= rect.get_area() <= area * .90:
            candidates.append(('embedded_image', rect))
    # Vector charts and diagrams often appear as connected drawing groups.
    drawings = page.get_drawings()
    if drawings:
        for rect in page.cluster_drawings(drawings=drawings):
            rect = pymupdf.Rect(rect) & page.rect
            if area * .04 <= rect.get_area() <= area * .80:
                candidates.append(('vector_group', rect))
    result: list[tuple[str, pymupdf.Rect]] = []
    for kind, rect in sorted(candidates, key=lambda value: value[1].get_area(), reverse=True):
        if any((rect & old).get_area() / max(1, rect.get_area()) > .75 for _, old in result):
            continue
        result.append((kind, rect))
    return result[:12]


def process_document(source: Path, raw_root: Path, run_root: Path) -> dict:
    relative = source.resolve().relative_to(raw_root.resolve()).as_posix()
    document_hash = digest_file(source)
    doc_id = safe_slug(source.stem) + '-' + document_hash[:10]
    destination = run_root / doc_id
    destination.mkdir(parents=True, exist_ok=True)
    summary = {'document': relative, 'sha256': document_hash, 'document_id': doc_id,
               'status': 'running', 'pages': 0, 'figure_candidates': 0,
               'needs_ocr_pages': [], 'ocr_pages': [], 'started_at': datetime.now(timezone.utc).isoformat()}
    write_json(destination / 'manifest.json', summary)
    try:
        with pymupdf.open(source) as pdf:
            if pdf.needs_pass:
                raise ValueError('Password-protected PDF requires review')
            summary['pages'] = pdf.page_count
            for page_index, page in enumerate(pdf):
                page_number = page_index + 1
                folder = destination / 'pages' / f'page-{page_number:03d}'
                folder.mkdir(parents=True, exist_ok=True)
                text = page.get_text('text', sort=True).strip()
                words = page.get_text('words', sort=True)
                if len(text) < 40:
                    source_png = folder / 'source.png'
                    page.get_pixmap(matrix=pymupdf.Matrix(1.8, 1.8), alpha=False).save(source_png)
                    try:
                        ocr = subprocess.run(['tesseract', str(source_png), 'stdout', '-l', 'eng'],
                                             capture_output=True, text=True, timeout=120, check=True)
                        if ocr.stdout.strip():
                            text = ocr.stdout.strip()
                            summary['ocr_pages'].append(page_number)
                        else:
                            summary['needs_ocr_pages'].append(page_number)
                    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        summary['needs_ocr_pages'].append(page_number)
                (folder / 'page.md').write_text(f'# Page {page_number}\n\n{text}\n', encoding='utf-8')
                figures = []
                figure_html = []
                for number, (kind, rect) in enumerate(figure_regions(page), start=1):
                    crop = f'figure-{number:02d}.png'
                    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect, alpha=False).save(folder / crop)
                    inside = [str(word[4]) for word in words if rect.contains(pymupdf.Point((word[0]+word[2])/2, (word[1]+word[3])/2))]
                    native = ' '.join(inside)
                    figure = {'id': f'page-{page_number:03d}-figure-{number:02d}', 'kind': kind,
                              'box_pdf_points': [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                              'crop': crop, 'native_text': native,
                              'percent_tokens': re.findall(r'\d+(?:\.\d+)?%', native),
                              'spec_type': 'source_crop', 'semantic_chart_status': 'needs_review'}
                    figures.append(figure)
                    label = native[:160].strip() or f'Figure {number} on page {page_number}'
                    figure_html.append(f'<figure><img src="{html.escape(crop)}" alt="{html.escape(label, quote=True)}"><figcaption>{html.escape(label)}</figcaption></figure>')
                summary['figure_candidates'] += len(figures)
                write_json(folder / 'figure-specs.json', {'schema_version': 1, 'source_pdf_sha256': document_hash,
                           'page': page_number, 'figures': figures,
                           'note': 'Source-faithful crops; chart values and geometry require review before semantic reconstruction.'})
                content = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Page %d</title><style>body{max-width:52rem;margin:2rem auto;font:16px/1.5 system-ui}img{max-width:100%%}pre{white-space:pre-wrap}</style><main><h1>Page %d</h1><pre>%s</pre>%s</main></html>' % (page_number, page_number, html.escape(text), ''.join(figure_html))
                (folder / 'page.html').write_text(content, encoding='utf-8')
        summary.update(assemble_source_evidence_specs(source, destination, doc_id, relative))
        summary['status'] = 'completed_with_review' if summary['needs_ocr_pages'] or summary['ocr_pages'] or summary['figure_candidates'] else 'completed'
    except Exception as exc:
        summary['status'] = 'failed'
        summary['error'] = f'{type(exc).__name__}: {exc}'
    summary['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_json(destination / 'manifest.json', summary)
    return summary
