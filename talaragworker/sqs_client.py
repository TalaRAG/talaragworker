from __future__ import annotations

from typing import Any

import boto3

from talaragworker.config import Settings


class SQSClient:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = self._resolve_queue_url(settings.sqs_queue)
        self._wait_time_seconds = settings.sqs_wait_time_seconds

    def _resolve_queue_url(self, queue_reference: str) -> str:
        if queue_reference.startswith("https://"):
            return queue_reference

        response = self._client.get_queue_url(QueueName=queue_reference)
        return response["QueueUrl"]

    def receive_message(self) -> dict[str, Any] | None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self._wait_time_seconds,
            VisibilityTimeout=300,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        return messages[0] if messages else None

    def delete_message(self, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
