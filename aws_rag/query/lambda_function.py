"""Lambda entry point for the RAG query API and UI.

app.py, rag_core.py and index.html started as copies of the retired Vercel app
(../e2e_RAG/vercel_app); this module only adapts them to Lambda.
"""

import os
from pathlib import Path

import boto3

# app.py reads DATABASE_URL from the environment. Load it from an SSM
# SecureString parameter once per cold start, before import. Bedrock calls use
# the Lambda's IAM role.
os.environ.setdefault(
    "DATABASE_URL",
    boto3.client("ssm").get_parameter(
        Name=os.environ["DATABASE_URL_PARAMETER"], WithDecryption=True
    )["Parameter"]["Value"],
)

from fastapi.responses import HTMLResponse  # noqa: E402
from mangum import Mangum  # noqa: E402

from app import app  # noqa: E402

INDEX_HTML = (Path(__file__).parent / "index.html").read_text()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return INDEX_HTML


handler = Mangum(app, lifespan="off")
