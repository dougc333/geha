"""Populate Terraform-managed model secrets from the local Compose API container.

Never prints a key. Run only after Terraform creates the empty secret records.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import boto3


NAMES = ("ANTHROPIC_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY")
ROOT = Path(__file__).resolve().parents[1]


def container_value(name: str) -> str:
    command = ["docker", "compose", "exec", "-T", "ingestion-workflow", "python", "-c",
               "import os,sys; print(os.environ.get(sys.argv[1], ''), end='')", name]
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="geha-terraform")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--project-name", default="geha-aws-ingestion")
    parser.add_argument("--execute", action="store_true", help="Transfer key values to AWS Secrets Manager")
    args = parser.parse_args()
    client = (boto3.Session(profile_name=args.profile, region_name=args.region).client("secretsmanager")
              if args.execute else None)
    for name in NAMES:
        secret_id = f"{args.project_name}/{name}"
        value = container_value(name)
        if not value:
            print(f"{name}: absent locally; skipped")
            continue
        if not args.execute:
            print(f"{name}: present locally; would write {secret_id}")
            continue
        client.put_secret_value(SecretId=secret_id, SecretString=value)
        print(f"{name}: stored in {secret_id}")


if __name__ == "__main__":
    main()
