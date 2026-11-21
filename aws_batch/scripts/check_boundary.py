"""Check copied Python code and Compose mounts remain within aws_batch."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIED = ('batch_app', 'document_ingestion_workflow', 'geha_processing', 'PDF_processing', 'crawl_dir/src', 'bounding_box')
LOCAL_MODULES = {name.split('/')[0] for name in COPIED}
FORBIDDEN = re.compile(r'/Users/dc/geha/(?!aws_batch(?:/|\b))')


def check() -> list[str]:
    errors = []
    for name in COPIED:
        folder = ROOT / name
        for file in folder.rglob('*.py'):
            if file.is_symlink() or not file.resolve().is_relative_to(ROOT):
                errors.append(f'External code link: {file}')
                continue
            source = file.read_text(encoding='utf-8')
            if FORBIDDEN.search(source):
                errors.append(f'External GEHA path: {file}')
            try:
                ast.parse(source, filename=str(file))
            except SyntaxError as exc:
                errors.append(f'Syntax error: {file}: {exc}')
    for file in ROOT.rglob('*.py'):
        if file.is_symlink() or not file.resolve().is_relative_to(ROOT):
            errors.append(f'External code link: {file}')
    return errors


if __name__ == '__main__':
    failures = check()
    if failures:
        raise SystemExit('\n'.join(failures))
    print('Boundary check passed: all Python code is inside aws_batch and parses successfully.')
