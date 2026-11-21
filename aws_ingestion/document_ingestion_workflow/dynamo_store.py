"""DynamoDB run/event store with the same interface as the local SQLite store."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from .run_store import TERMINAL_STATUSES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DynamoRunStore:
    def __init__(self, table_name: str | None = None, table: Any = None) -> None:
        self.table_name = table_name or os.environ["INGESTION_STATE_TABLE"]
        self.table = table or boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2")).Table(self.table_name)

    def create(self, run_id: str, document: str) -> None:
        now = _now()
        self.table.put_item(
            Item={"run_id": run_id, "record_key": "META", "document": document,
                  "status": "queued", "last_event_seq": 0, "created_at": now, "updated_at": now},
            ConditionExpression="attribute_not_exists(run_id)",
        )

    def get(self, run_id: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"run_id": run_id, "record_key": "META"}, ConsistentRead=True).get("Item")
        return dict(item) if item else None

    def mark_running(self, run_id: str) -> None:
        now = _now()
        try:
            self.table.update_item(
                Key={"run_id": run_id, "record_key": "META"},
                UpdateExpression="SET #status = :running, started_at = if_not_exists(started_at, :now), updated_at = :now",
                ConditionExpression="attribute_exists(run_id) AND #status <> :succeeded AND #status <> :failed AND #status <> :cancelled",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":running": "running", ":now": now,
                                           ":succeeded": "succeeded", ":failed": "failed", ":cancelled": "cancelled"},
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            return

    def append_event(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        result = self.table.update_item(
            Key={"run_id": run_id, "record_key": "META"},
            UpdateExpression="ADD last_event_seq :one SET updated_at = :now",
            ConditionExpression="attribute_exists(run_id)",
            ExpressionAttributeValues={":one": 1, ":now": now},
            ReturnValues="UPDATED_NEW",
        )
        seq = int(result["Attributes"]["last_event_seq"])
        stored = {**event, "seq": seq, "at": now}
        self.table.put_item(Item={"run_id": run_id, "record_key": f"EVENT#{seq:012d}",
                                  "payload": json.dumps(stored), "created_at": now})
        return stored

    def finish(self, run_id: str, status: str, error: dict[str, Any] | None = None) -> None:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid terminal status: {status}")
        now = _now()
        self.table.update_item(
            Key={"run_id": run_id, "record_key": "META"},
            UpdateExpression="SET #status = :status, #error = :error, finished_at = :now, updated_at = :now",
            ConditionExpression="attribute_exists(run_id)",
            ExpressionAttributeNames={"#status": "status", "#error": "error"},
            ExpressionAttributeValues={":status": status, ":error": json.dumps(error) if error else "",
                                       ":now": now},
        )

    def snapshot(self, run_id: str, offset: int) -> tuple[list[dict[str, Any]], bool]:
        run = self.get(run_id)
        if run is None:
            raise KeyError(f"Unknown run: {run_id}")
        events = []
        response = self.table.query(
            KeyConditionExpression=Key("run_id").eq(run_id) & Key("record_key").between(f"EVENT#{offset + 1:012d}", "EVENT#~"),
            ConsistentRead=True,
        )
        while True:
            events.extend(json.loads(item["payload"]) for item in response.get("Items", []))
            if "LastEvaluatedKey" not in response:
                break
            response = self.table.query(
                KeyConditionExpression=Key("run_id").eq(run_id) & Key("record_key").between(f"EVENT#{offset + 1:012d}", "EVENT#~"),
                ConsistentRead=True, ExclusiveStartKey=response["LastEvaluatedKey"],
            )
        return events, run["status"] in TERMINAL_STATUSES
