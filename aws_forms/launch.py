"""Upload the reviewed alt-2 PDF and start one on-demand Fargate task."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3


def _outputs(terraform_dir: Path) -> dict[str, object]:
    result = subprocess.run(
        ["terraform", "output", "-json"], cwd=terraform_dir,
        check=True, text=True, capture_output=True,
    )
    return {key: record["value"] for key, record in json.loads(result.stdout).items()}


def launch(pdf: Path, terraform_dir: Path, profile: str | None = None) -> dict[str, str]:
    outputs = _outputs(terraform_dir)
    with pdf.open("rb") as stream:
        actual_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual_hash != outputs["source_sha256"]:
        raise ValueError("This first worker accepts only the reviewed alt-2 PDF")

    session = boto3.Session(profile_name=profile)
    s3 = session.client("s3")
    ecs = session.client("ecs")
    run_id = "aws-forms-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    bucket = str(outputs["bucket_name"])
    input_key = f"incoming/{run_id}/source.pdf"
    s3.upload_file(str(pdf), bucket, input_key, ExtraArgs={"ContentType": "application/pdf"})
    response = ecs.run_task(
        cluster=str(outputs["ecs_cluster_arn"]),
        taskDefinition=str(outputs["task_definition_arn"]),
        launchType="FARGATE",
        networkConfiguration={"awsvpcConfiguration": {
            "subnets": list(outputs["public_subnet_ids"]),
            "securityGroups": [str(outputs["task_security_group_id"])],
            "assignPublicIp": "ENABLED",
        }},
        overrides={"containerOverrides": [{"name": "forms-worker", "environment": [
            {"name": "AWS_FORMS_RUN_ID", "value": run_id},
            {"name": "AWS_FORMS_INPUT_KEY", "value": input_key},
        ]}]},
    )
    if response.get("failures") or not response.get("tasks"):
        raise RuntimeError(f"ECS did not start the task: {response.get('failures')}")
    return {
        "run_id": run_id,
        "task_arn": response["tasks"][0]["taskArn"],
        "bucket": bucket,
        "status_key": f"runs/{run_id}/status.json",
        "input_key": input_key,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--terraform-dir", type=Path,
                        default=Path(__file__).resolve().parent / "terraform")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()
    print(json.dumps(launch(args.pdf.resolve(), args.terraform_dir.resolve(), args.profile), indent=2))


if __name__ == "__main__":
    main()
