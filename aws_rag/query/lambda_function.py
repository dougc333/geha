"""Lambda entry point for the RAG query API, the lab UI (/) and the chatbot (/chat).

app.py, rag_core.py and index.html started as copies of the retired Vercel app
(../e2e_bm25vector); this module only adapts them to Lambda.
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
    "SIGNUP_HASH_KEY": os.getenv("SIGNUP_HASH_KEY_PARAMETER"),
    "WEAVIATE_URL": os.getenv("WEAVIATE_URL_PARAMETER"),  # optional: Weaviate comparison
    "WEAVIATE_API_KEY": os.getenv("WEAVIATE_API_KEY_PARAMETER"),
    "API_KEY": os.getenv("API_KEY_PARAMETER"),  # shared access key for /api/*
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
    for required in ("DATABASE_URL", "API_KEY"):  # fail closed: never serve without the key
        if _SECRETS[required] and required not in os.environ:
            raise RuntimeError(f"SSM parameter {_SECRETS[required]} not found")

from fastapi.responses import HTMLResponse  # noqa: E402
from mangum import Mangum  # noqa: E402

from app import app, langfuse  # noqa: E402
from chat import router as chat_router  # noqa: E402
from signup.router import router as signup_router  # noqa: E402

app.include_router(chat_router)
app.include_router(signup_router)

INDEX_HTML = (Path(__file__).parent / "index.html").read_text()
CHAT_HTML = (Path(__file__).parent / "chat.html").read_text()
BACKENDS_HTML = (Path(__file__).parent / "backends.html").read_text()
SIGNUP_HTML = (Path(__file__).parent / "signup.html").read_text()


# no-cache: browsers revalidate, so a deploy's UI changes show on the next load.
NO_CACHE = {"Cache-Control": "no-cache"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML, headers=NO_CACHE)


@app.get("/chat", response_class=HTMLResponse, include_in_schema=False)
def chat_page() -> HTMLResponse:
    return HTMLResponse(CHAT_HTML, headers=NO_CACHE)


@app.get("/backends", response_class=HTMLResponse, include_in_schema=False)
def backends_page() -> HTMLResponse:
    return HTMLResponse(BACKENDS_HTML, headers=NO_CACHE)


@app.get("/signup", response_class=HTMLResponse, include_in_schema=False)
def signup_page() -> HTMLResponse:
    return HTMLResponse(SIGNUP_HTML, headers=NO_CACHE)


_asgi = Mangum(app, lifespan="off")


def handler(event, context):
    try:
        return _asgi(event, context)
    finally:
        # Lambda freezes between requests; send buffered traces and scores now.
        langfuse.flush()
