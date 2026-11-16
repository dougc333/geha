"""Launch one temporary Docling ECS task for each incoming PDF."""

import json
import os
from urllib.parse import unquote_plus

import boto3


ecs = boto3.client("ecs")
s3 = boto3.client("s3")


def handler(event, context):
    launched = []
    for item in event["Records"]:
        source = item["s3"]
        bucket = source["bucket"]["name"]
        key = unquote_plus(source["object"]["key"])
        if not key.startswith("incoming/") or not key.lower().endswith(".pdf"):
            continue

        output_key = "extracted/" + key[len("incoming/") : -4] + ".md"
        source_url = s3.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=21600
        )
        output_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": os.environ["OUTPUT_BUCKET"],
                "Key": output_key,
                "ContentType": "text/markdown; charset=utf-8",
            },
            ExpiresIn=21600,
        )
        result = ecs.run_task(
            cluster=os.environ["ECS_CLUSTER"],
            taskDefinition=os.environ["TASK_DEFINITION"],
            launchType="FARGATE",
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": json.loads(os.environ["PUBLIC_SUBNETS"]),
                    "securityGroups": [os.environ["TASK_SECURITY_GROUP"]],
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [{
                    "name": "docling-worker",
                    "environment": [
                        {"name": "SOURCE_URL", "value": source_url},
                        {"name": "OUTPUT_URL", "value": output_url},
                    ],
                }]
            },
        )
        if result.get("failures") or not result.get("tasks"):
            raise RuntimeError(f"ECS rejected {key}: {result.get('failures')}")
        launched.append({"source": key, "output": output_key, "task": result["tasks"][0]["taskArn"]})
    return {"launched": launched}
