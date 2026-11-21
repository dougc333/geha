"""SQS-compatible job delivery for ElasticMQ locally and SQS in AWS."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import boto3


@dataclass(frozen=True)
class ReceivedJob:
    receipt_handle: str
    payload: dict[str, Any]


class ElasticJobQueue:
    def __init__(self) -> None:
        self.queue_name = os.getenv("INGESTION_QUEUE_NAME", "document-ingestion")
        self.endpoint_url = os.getenv("SQS_ENDPOINT_URL") or None
        self.client = boto3.client(
            "sqs",
            endpoint_url=self.endpoint_url,
            region_name=os.getenv("AWS_REGION", "us-west-2"),
            aws_access_key_id=("local" if self.endpoint_url else None),
            aws_secret_access_key=("local" if self.endpoint_url else None),
        )
        self._queue_url: str | None = os.getenv("INGESTION_QUEUE_URL") or None

    @property
    def queue_url(self) -> str:
        if self._queue_url is None:
            if not self.endpoint_url:
                raise RuntimeError("INGESTION_QUEUE_URL must name a Terraform-provisioned SQS queue in AWS mode")
            response = self.client.create_queue(
                QueueName=self.queue_name,
                Attributes={
                    "VisibilityTimeout": os.getenv("SQS_VISIBILITY_TIMEOUT", "900"),
                    "ReceiveMessageWaitTimeSeconds": "10",
                },
            )
            self._queue_url = response["QueueUrl"]
        return self._queue_url

    def send(self, payload: dict[str, Any]) -> str:
        response = self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(payload),
        )
        return response["MessageId"]

    def receive(self) -> ReceivedJob | None:
        response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            VisibilityTimeout=int(os.getenv("SQS_VISIBILITY_TIMEOUT", "900")),
        )
        messages = response.get("Messages", [])
        if not messages:
            return None
        message = messages[0]
        return ReceivedJob(
            receipt_handle=message["ReceiptHandle"],
            payload=json.loads(message["Body"]),
        )

    def acknowledge(self, job: ReceivedJob) -> None:
        self.client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=job.receipt_handle,
        )

    def extend_visibility(self, job: ReceivedJob) -> None:
        self.client.change_message_visibility(
            QueueUrl=self.queue_url,
            ReceiptHandle=job.receipt_handle,
            VisibilityTimeout=int(os.getenv("SQS_VISIBILITY_TIMEOUT", "900")),
        )
