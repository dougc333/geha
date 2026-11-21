"""Consistent JSON, JSONL, and hashing helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _temporary_path(path: Path) -> tuple[int, Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    return descriptor, Path(name)


def atomic_json(
    path: Path,
    value: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> None:
    descriptor, temporary = _temporary_path(path)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(
                value,
                stream,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys,
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(
    path: Path,
    records: Iterable[dict[str, Any]],
    *,
    atomic: bool = False,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    temporary = path
    if atomic:
        descriptor, temporary = _temporary_path(path)
    count = 0
    try:
        if descriptor is None:
            stream = temporary.open("w", encoding="utf-8")
        else:
            stream = os.fdopen(descriptor, "w", encoding="utf-8")
        with stream:
            for record in records:
                stream.write(
                    json.dumps(
                        record,
                        ensure_ascii=ensure_ascii,
                        sort_keys=sort_keys,
                    )
                    + "\n"
                )
                count += 1
            if atomic:
                stream.flush()
                os.fsync(stream.fileno())
        if atomic:
            os.replace(temporary, path)
    except BaseException:
        if atomic:
            temporary.unlink(missing_ok=True)
        raise
    return count


def atomic_jsonl(
    path: Path,
    records: Iterable[dict[str, Any]],
    *,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> int:
    return write_jsonl(
        path,
        records,
        atomic=True,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
    )
