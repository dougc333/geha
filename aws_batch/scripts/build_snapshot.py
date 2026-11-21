"""Copy catalog PDFs into this workspace while preserving raw relative paths."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build(manifest_path: Path, raw_root: Path, workspace: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    output = workspace / 'crawl_dir' / 'raw'
    records = []
    for item in manifest['documents']:
        record = {key: item.get(key) for key in ('title', 'url', 'filename', 'type', 'last_updated', 'status', 'sha256')}
        if item['status'] == 'failed':
            record['error'] = item['error']
        else:
            source = Path(item.get('path') or item['existing_path']).resolve()
            relative = source.relative_to(raw_root.resolve())
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or sha256(target) != item['sha256']:
                shutil.copy2(source, target)
            if sha256(target) != item['sha256']:
                raise ValueError(f'Snapshot hash mismatch: {relative}')
            record['relative_path'] = relative.as_posix()
            record['bytes'] = target.stat().st_size
        records.append(record)
    result = {'source': manifest['source'], 'checked_at': manifest['checked_at'],
              'counts': manifest['counts'], 'documents': records}
    (workspace / 'catalog.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--raw-root', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = build(args.manifest, args.raw_root, args.workspace)
    print(f"Snapshotted {sum(bool(x.get('relative_path')) for x in result['documents'])} PDFs")


if __name__ == '__main__':
    main()
