"""Lambda entry point for the RAG query API, the lab UI (/) and the chatbot (/chat).

app.py, rag_core.py and index.html started as copies of the retired Vercel app
(../e2e_RAG/vercel_app); this module only adapts them to Lambda.
"""

import os
from pathlib import Path

import boto3

# app.py reads DATABASE_URL and the Langfuse keys from the environment. Load
# them from SSM SecureString parameters once per cold start, before import.
# Bedrock calls use the Lambda's IAM role. Langfuse keys are optional: without
# them tracing is disabled.
_SECRETS = {
    "DATABASE_URL": os.environ["DATABASE_URL_PARAMETER"],
    "LANGFUSE_PUBLIC_KEY": os.getenv("LANGFUSE_PUBLIC_KEY_PARAMETER"),
    "LANGFUSE_SECRET_KEY": os.getenv("LANGFUSE_SECRET_KEY_PARAMETER"),
}
_wanted = {env: name for env, name in _SECRETS.items() if name and env not in os.environ}
if _wanted:
    _found = {
        p["Name"]: p["Value"]
        for p in boto3.client("ssm").get_parameters(
            Names=list(_wanted.values()), WithDecryption=True
        )["Parameters"]
    }
    for env, name in _wanted.items():
        if name in _found:
            os.environ[env] = _found[name]
    if "DATABASE_URL" not in os.environ:
        raise RuntimeError(f"SSM parameter {_SECRETS['DATABASE_URL']} not found")

from fastapi.responses import HTMLResponse  # noqa: E402
from mangum import Mangum  # noqa: E402

from app import app, langfuse  # noqa: E402
from chat import router as chat_router  # noqa: E402

app.include_router(chat_router)

INDEX_HTML = (Path(__file__).parent / "index.html").read_text()
CHAT_HTML = (Path(__file__).parent / "chat.html").read_text()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return INDEX_HTML


@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
def chat_page() -> str:
    return CHAT_HTML


_asgi = Mangum(app, lifespan="off")


def handler(event, context):
    try:
        return _asgi(event, context)
    finally:
        # Lambda freezes between requests; send buffered traces and scores now.
        langfuse.flush()
