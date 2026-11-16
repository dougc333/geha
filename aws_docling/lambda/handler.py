"""Launch one temporary Docling ECS task for each incoming PDF."""

import json
import os
from urllib.parse import unquote_plus

import boto3


ecs = boto3.client("ecs")
region = os.environ["AWS_REGION"]
s3 = boto3.client(
    "s3", region_name=region, endpoint_url=f"https://s3.{region}.amazonaws.com"
)


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
        stem = key[len("incoming/") : -4]
        figures_key = f"extracted/{stem}.figures.zip"
        models_key = f"extracted/{stem}.models.json"
        figures_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": figures_key, "ContentType": "application/zip"},
            ExpiresIn=21600,
        )
        models_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": models_key, "ContentType": "application/json"},
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
                        {"name": "FIGURES_URL", "value": figures_url},
                        {"name": "MODELS_URL", "value": models_url},
                    ],
                }]
            },
        )
        if result.get("failures") or not result.get("tasks"):
            raise RuntimeError(f"ECS rejected {key}: {result.get('failures')}")
        task_arn = result["tasks"][0]["taskArn"]
        log_key = f"jobs/logs/{task_arn.rsplit('/', 1)[-1]}.log"
        job_key = "jobs/" + key[len("incoming/") : -4] + ".json"
        s3.put_object(
            Bucket=bucket,
            Key=job_key,
            Body=json.dumps({"source": key, "output": output_key, "figures": figures_key, "models": models_key, "task": task_arn, "log": log_key}).encode(),
            ContentType="application/json",
        )
        launched.append({"source": key, "output": output_key, "task": task_arn})
    return {"launched": launched}
