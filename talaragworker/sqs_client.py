from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from threading import Event, Thread
from typing import Any

import boto3

from talaragworker.config import Settings


class MessageVisibilityLease(AbstractContextManager["MessageVisibilityLease"]):
    def __init__(
        self,
        sqs_client: "SQSClient",
        receipt_handle: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self._sqs_client = sqs_client
        self._receipt_handle = receipt_handle
        self._logger = logger
        self._stop_event = Event()
        self._thread: Thread | None = None

    def __enter__(self) -> "MessageVisibilityLease":
        self._thread = Thread(target=self._run, name="sqs-visibility-lease", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self._sqs_client.visibility_heartbeat_seconds + 1)

    def _run(self) -> None:
        while not self._stop_event.wait(self._sqs_client.visibility_heartbeat_seconds):
            try:
                self._sqs_client.change_message_visibility(
                    self._receipt_handle,
                    self._sqs_client.visibility_timeout_seconds,
                )
                if self._logger is not None:
                    self._logger.info(
                        "Extended SQS visibility timeout to %s seconds",
                        self._sqs_client.visibility_timeout_seconds,
                    )
            except Exception:
                if self._logger is not None:
                    self._logger.exception("Failed to extend SQS visibility timeout")
                return


class SQSClient:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client("sqs", region_name=settings.aws_region)
        self._queue_url = self._resolve_queue_url(settings.sqs_queue)
        self._visibility_timeout_seconds = settings.sqs_visibility_timeout_seconds
        self._visibility_heartbeat_seconds = settings.sqs_visibility_heartbeat_seconds
        self._wait_time_seconds = settings.sqs_wait_time_seconds
        self.ensure_queue_is_reachable_and_fifo()

    def _resolve_queue_url(self, queue_reference: str) -> str:
        if queue_reference.startswith("https://"):
            return queue_reference

        response = self._client.get_queue_url(QueueName=queue_reference)
        return response["QueueUrl"]

    @property
    def visibility_timeout_seconds(self) -> int:
        return self._visibility_timeout_seconds

    @property
    def visibility_heartbeat_seconds(self) -> int:
        return self._visibility_heartbeat_seconds

    def ensure_queue_is_reachable_and_fifo(self) -> None:
        attributes = self._client.get_queue_attributes(
            QueueUrl=self._queue_url,
            AttributeNames=["FifoQueue"],
        ).get("Attributes", {})
        if attributes.get("FifoQueue") != "true":
            raise ValueError(f"SQS_QUEUE must reference a FIFO queue: {self._queue_url}")

    def receive_message(self) -> dict[str, Any] | None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self._wait_time_seconds,
            VisibilityTimeout=self._visibility_timeout_seconds,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        messages = response.get("Messages", [])
        return messages[0] if messages else None

    def lease_message(
        self,
        receipt_handle: str,
        logger: logging.Logger | None = None,
    ) -> MessageVisibilityLease:
        return MessageVisibilityLease(self, receipt_handle, logger)

    def change_message_visibility(self, receipt_handle: str, visibility_timeout: int) -> None:
        self._client.change_message_visibility(
            QueueUrl=self._queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=visibility_timeout,
        )

    def delete_message(self, receipt_handle: str) -> None:
        self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt_handle)
