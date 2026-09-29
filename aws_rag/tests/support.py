"""Shared setup for aws_rag unit tests: fake environment and path-based imports.

The Lambdas read settings at import time and create boto3 clients (which need a
region but no credentials), so the environment is set before any of them are
imported. Nothing here talks to AWS, Neon, Weaviate or Langfuse.

    uv run --no-project --with-requirements aws_rag/query/requirements.txt \
        --with boto3 --with httpx --with pymupdf python -m unittest discover -s aws_rag/tests
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # aws_rag/

os.environ.update({
    "AWS_REGION": "us-west-2",
    "AWS_DEFAULT_REGION": "us-west-2",
    # Fake credentials, and no ~/.aws config: tests must never use a real login.
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_CONFIG_FILE": os.devnull,
    "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
    "LANGFUSE_TRACING_ENABLED": "false",
    "DATABASE_URL_PARAMETER": "/test/database-url",
    "DATABASE_URL": "postgresql://test:test@localhost:1/test",  # never connected to
    "API_KEY": "test-key",
})
for name in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY",
             "WEAVIATE_URL", "WEAVIATE_API_KEY"):
    os.environ.pop(name, None)

# query/ modules import each other by name (app, chat, library, rag_core).
sys.path.insert(0, str(ROOT / "query"))


def load(name: str, relative_path: str):
    """Import a file under a unique module name: chunker/, embedder/ and query/
    each have their own handler.py or rag_core.py."""
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
