"""S3-backed GEHA catalog API and download worker.

The API never writes to a local crawl directory. Catalog state lives in S3 and
download status is indexed in DynamoDB. The same module is used by API Gateway
and by the Step Functions Map worker.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

import boto3


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
sfn = boto3.client("stepfunctions")

CATALOG_BUCKET = os.environ["CATALOG_BUCKET"]
CATALOG_KEY = os.environ.get("CATALOG_KEY", "catalog/inventory-snapshot.json")
DOCUMENT_BUCKET = os.environ["DOCUMENT_BUCKET"]
TABLE_NAME = os.environ["TABLE_NAME"]
DOWNLOADER_FUNCTION = os.environ.get("DOWNLOADER_FUNCTION", "")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")
ALLOWED_HOSTS = {"www.geha.com", "geha.com", "www.mygeha.com", "mygeha.com"}
MAX_BYTES = 100 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def response(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-headers": "content-type",
            "access-control-allow-methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def catalog() -> dict[str, Any]:
    obj = s3.get_object(Bucket=CATALOG_BUCKET, Key=CATALOG_KEY)
    payload = json.loads(obj["Body"].read())
    if not isinstance(payload.get("assets"), list):
        raise ValueError("Catalog must contain an assets array")
    return payload


def asset_by_id(asset_id: str) -> dict[str, Any]:
    match = next((item for item in catalog()["assets"] if item.get("id") == asset_id), None)
    if not match:
        raise KeyError(asset_id)
    return match


def set_status(asset: dict[str, Any], **updates: Any) -> None:
    table = dynamodb.Table(TABLE_NAME)
    values = {"asset_id": asset["id"], "updated_at": now(), **updates}
    names = {"#status": "status"}
    expressions = ["#status = :status", "updated_at = :updated_at"]
    attributes = {":status": values.get("status", "queued"), ":updated_at": values["updated_at"]}
    for key, value in values.items():
        if key in {"asset_id", "updated_at", "status"} or value is None:
            continue
        names[f"#{key}"] = key
        expressions.append(f"#{key} = :{key}")
        attributes[f":{key}"] = value
    table.update_item(
        Key={"asset_id": asset["id"]},
        UpdateExpression="SET " + ", ".join(expressions),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=attributes,
    )


def destination_key(asset: dict[str, Any]) -> str:
    parsed = urllib.parse.urlparse(str(asset["url"]))
    filename = os.path.basename(parsed.path) or f"{asset['id']}.pdf"
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename)
    return f"documents/{asset['id']}/{filename}"


def download_asset(asset: dict[str, Any]) -> dict[str, Any]:
    url = str(asset.get("url", ""))
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or not url.lower().split("?", 1)[0].endswith(".pdf"):
        raise ValueError("Only HTTPS GEHA PDF URLs are allowed")
    key = destination_key(asset)
    set_status(asset, status="downloading", source_url=url, s3_key=key)
    request = urllib.request.Request(url, headers={"User-Agent": "geha-context-downloader/1.0"})
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=60) as source:
            declared = int(source.headers.get("Content-Length", "0") or 0)
            if declared > MAX_BYTES:
                raise ValueError("PDF exceeds the 100 MB safety limit")
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("PDF exceeds the 100 MB safety limit")
                digest.update(chunk)
                chunks.append(chunk)
    except Exception as exc:
        set_status(asset, status="failed", error=str(exc))
        raise
    s3.put_object(
        Bucket=DOCUMENT_BUCKET,
        Key=key,
        Body=b"".join(chunks),
        ContentType="application/pdf",
        Metadata={"source-url": url, "asset-id": asset["id"], "sha256": digest.hexdigest()},
        ServerSideEncryption="aws:kms",
    )
    result = {"status": "downloaded", "s3_key": key, "sha256": digest.hexdigest(), "bytes": total}
    set_status(asset, **result)
    return {"asset_id": asset["id"], **result}


def worker(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    asset = event.get("asset") if isinstance(event.get("asset"), dict) else event
    return download_asset(asset)


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(204, {})
    route = event.get("rawPath") or event.get("path") or "/"
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    try:
        if method == "GET" and route == "/api/inventory":
            payload = catalog()
            statuses = dynamodb.Table(TABLE_NAME).scan(ProjectionExpression="asset_id, #status, s3_key, sha256, bytes, error, updated_at", ExpressionAttributeNames={"#status": "status"}).get("Items", [])
            by_id = {item["asset_id"]: item for item in statuses}
            assets = [{**asset, **by_id.get(asset["id"], {})} for asset in payload["assets"]]
            return response(200, {**payload, "assets": assets, "storage": {"bucket": DOCUMENT_BUCKET, "prefix": "documents/"}})
        if method == "POST" and route == "/api/download":
            body = json.loads(event.get("body") or "{}")
            asset = asset_by_id(str(body.get("asset_id", "")))
            if not DOWNLOADER_FUNCTION:
                return response(500, {"error": "DOWNLOADER_FUNCTION is not configured"})
            set_status(asset, status="queued", source_url=asset["url"])
            lambda_client.invoke(FunctionName=DOWNLOADER_FUNCTION, InvocationType="Event", Payload=json.dumps({"asset": asset}).encode())
            return response(202, {"asset_id": asset["id"], "status": "queued"})
        if method == "POST" and route == "/api/download-all":
            if not STATE_MACHINE_ARN:
                return response(500, {"error": "STATE_MACHINE_ARN is not configured"})
            assets = catalog()["assets"]
            execution = sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, input=json.dumps({"assets": assets}))
            return response(202, {"execution_arn": execution["executionArn"], "count": len(assets), "status": "started"})
        return response(404, {"error": "Not found"})
    except KeyError as exc:
        return response(404, {"error": f"Unknown asset: {exc.args[0]}"})
    except Exception as exc:
        return response(500, {"error": str(exc)})
