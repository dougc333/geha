"""Archive one stopped Docling task's CloudWatch stream to S3."""

import json
import os
import time

import boto3


logs = boto3.client("logs")
s3 = boto3.client("s3")


def _read_stream(group: str, stream: str) -> list[dict]:
    events = []
    token = None
    for _ in range(100):
        params = {"logGroupName": group, "logStreamName": stream, "startFromHead": True}
        if token:
            params["nextToken"] = token
        response = logs.get_log_events(**params)
        events.extend({"timestamp": item["timestamp"], "message": item["message"]}
                      for item in response["events"])
        next_token = response["nextForwardToken"]
        if next_token == token:
            return events
        token = next_token
    raise RuntimeError(f"CloudWatch log stream pagination did not finish: {stream}")


def handler(event, context):
    detail = event["detail"]
    if detail.get("lastStatus") != "STOPPED":
        return {"skipped": "task has not stopped"}
    task_arn = detail["taskArn"]
    task_id = task_arn.rsplit("/", 1)[-1]
    container = next((item for item in detail.get("containers", [])
                      if item.get("name") == "docling-worker"), {})
    stream = container.get("logStreamName") or f"worker/docling-worker/{task_id}"
    group = os.environ["LOG_GROUP"]
    events = []
    missing_stream = False
    previous_count = -1
    for attempt in range(5):
        try:
            events = _read_stream(group, stream)
            if events and len(events) == previous_count:
                break
            previous_count = len(events)
        except logs.exceptions.ResourceNotFoundException:
            missing_stream = True
        if attempt < 4:
            time.sleep(2)
    header = {
        "task_arn": task_arn,
        "cluster_arn": detail.get("clusterArn"),
        "stopped_at": detail.get("stoppedAt"),
        "stop_code": detail.get("stopCode"),
        "stopped_reason": detail.get("stoppedReason"),
        "container_exit_code": container.get("exitCode"),
        "cloudwatch_log_group": group,
        "cloudwatch_log_stream": stream,
        "log_event_count": len(events),
        "no_log_events": not events,
        "stream_missing": missing_stream and not events,
    }
    body = json.dumps(header, indent=2) + "\n\n"
    body += "\n".join(item["message"].rstrip("\n") for item in events) + "\n"
    key = f"jobs/logs/{task_id}.log"
    s3.put_object(Bucket=os.environ["OUTPUT_BUCKET"], Key=key,
                  Body=body.encode("utf-8"), ContentType="text/plain; charset=utf-8")
    return {"key": key, "events": len(events)}
