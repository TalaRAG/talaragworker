import logging
import sys
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class SQSClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boto_client = MagicMock()
        self.boto3_module = SimpleNamespace(client=MagicMock(return_value=self.boto_client))
        self.module_patcher = patch.dict(sys.modules, {"boto3": self.boto3_module})
        self.module_patcher.start()
        sys.modules.pop("talaragworker.sqs_client", None)
        self.sqs_client_module = import_module("talaragworker.sqs_client")
        self.SQSClient = self.sqs_client_module.SQSClient

        self.settings = SimpleNamespace(
            aws_region="ap-southeast-1",
            sqs_queue="https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
            sqs_wait_time_seconds=20,
            sqs_visibility_timeout_seconds=1800,
            sqs_visibility_heartbeat_seconds=300,
        )

    def tearDown(self) -> None:
        self.module_patcher.stop()
        sys.modules.pop("talaragworker.sqs_client", None)

    def test_init_rejects_non_fifo_queue(self) -> None:
        self.boto_client.get_queue_attributes.return_value = {"Attributes": {"FifoQueue": "false"}}

        with self.assertRaisesRegex(ValueError, "SQS_QUEUE must reference a FIFO queue"):
            self.SQSClient(self.settings)

    def test_receive_message_uses_configured_visibility_timeout(self) -> None:
        self.boto_client.get_queue_attributes.return_value = {"Attributes": {"FifoQueue": "true"}}
        self.boto_client.receive_message.return_value = {"Messages": [{"Body": "{}"}]}

        client = self.SQSClient(self.settings)

        message = client.receive_message()

        self.assertEqual(message, {"Body": "{}"})
        self.boto_client.receive_message.assert_called_once_with(
            QueueUrl=self.settings.sqs_queue,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=self.settings.sqs_wait_time_seconds,
            VisibilityTimeout=self.settings.sqs_visibility_timeout_seconds,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )

    def test_visibility_lease_extends_message_timeout(self) -> None:
        self.boto_client.get_queue_attributes.return_value = {"Attributes": {"FifoQueue": "true"}}
        settings = SimpleNamespace(
            aws_region="ap-southeast-1",
            sqs_queue="https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
            sqs_wait_time_seconds=20,
            sqs_visibility_timeout_seconds=1800,
            sqs_visibility_heartbeat_seconds=5,
        )

        client = self.SQSClient(settings)
        logger = logging.getLogger("test")
        lease = client.lease_message("receipt-handle", logger)

        with patch.object(lease._stop_event, "wait", side_effect=[False, True]):
            with lease:
                pass

        self.boto_client.change_message_visibility.assert_called_once_with(
            QueueUrl=settings.sqs_queue,
            ReceiptHandle="receipt-handle",
            VisibilityTimeout=settings.sqs_visibility_timeout_seconds,
        )


if __name__ == "__main__":
    unittest.main()
