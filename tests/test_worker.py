import logging
import sys
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class WorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        fake_psycopg = SimpleNamespace(
            connect=MagicMock(),
            sql=SimpleNamespace(SQL=MagicMock(), Identifier=MagicMock()),
        )
        fake_boto3 = SimpleNamespace(client=MagicMock())
        fake_rows = SimpleNamespace(dict_row=MagicMock())
        fake_json = SimpleNamespace(Json=MagicMock())

        self.module_patcher = patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.sql": fake_psycopg.sql,
                "psycopg.rows": fake_rows,
                "psycopg.types": SimpleNamespace(json=fake_json),
                "psycopg.types.json": fake_json,
                "boto3": fake_boto3,
            },
        )
        self.module_patcher.start()
        sys.modules.pop("talaragworker.worker", None)
        self._process_message = import_module("talaragworker.worker")._process_message

    def tearDown(self) -> None:
        self.module_patcher.stop()
        sys.modules.pop("talaragworker.worker", None)

    def test_process_message_skips_duplicate_document_processing(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        database = MagicMock()
        sqs_client = MagicMock()
        s3_client = MagicMock()
        embedder = MagicMock()

        lease = MagicMock()
        lease.__enter__.return_value = lease
        lease.__exit__.return_value = None
        sqs_client.lease_message.return_value = lease
        database.fetch_document.return_value = MagicMock(s3_key="documents/sample-budget.txt")
        database.claim_document_for_processing.return_value = False

        self._process_message(
            logger,
            database,
            sqs_client,
            s3_client,
            embedder,
            {"ReceiptHandle": "receipt-1", "Body": '{"document_id":"doc-1","key":"documents/sample-budget.txt"}'},
        )

        database.claim_document_for_processing.assert_called_once_with("doc-1")
        sqs_client.delete_message.assert_called_once_with("receipt-1")
        s3_client.fetch_text.assert_not_called()
        embedder.embed_document.assert_not_called()

    def test_process_message_requires_key(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        database = MagicMock()
        sqs_client = MagicMock()
        s3_client = MagicMock()
        embedder = MagicMock()

        with self.assertRaisesRegex(RuntimeError, "SQS message is missing key"):
            self._process_message(
                logger,
                database,
                sqs_client,
                s3_client,
                embedder,
                {"ReceiptHandle": "receipt-1", "Body": '{"document_id":"doc-1"}'},
            )

        sqs_client.delete_message.assert_called_once_with("receipt-1")
        database.fetch_document.assert_not_called()

    def test_process_message_uses_payload_key_for_s3_fetch(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        database = MagicMock()
        sqs_client = MagicMock()
        s3_client = MagicMock()
        embedder = MagicMock()

        lease = MagicMock()
        lease.__enter__.return_value = lease
        lease.__exit__.return_value = None
        sqs_client.lease_message.return_value = lease
        database.fetch_document.return_value = MagicMock(s3_key="documents/stored-budget.txt")
        database.claim_document_for_processing.return_value = True
        s3_client.fetch_object.return_value = SimpleNamespace(body=b"Budget allocation", content_type="text/plain")
        embedder.embed_document.return_value = []

        self._process_message(
            logger,
            database,
            sqs_client,
            s3_client,
            embedder,
            {"ReceiptHandle": "receipt-1", "Body": '{"document_id":"doc-1","key":"documents/payload-budget.txt"}'},
        )

        s3_client.fetch_object.assert_called_once_with("documents/payload-budget.txt")

    def test_process_message_deletes_failed_message(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        database = MagicMock()
        sqs_client = MagicMock()
        s3_client = MagicMock()
        embedder = MagicMock()

        lease = MagicMock()
        lease.__enter__.return_value = lease
        lease.__exit__.return_value = None
        sqs_client.lease_message.return_value = lease
        database.fetch_document.return_value = MagicMock(s3_key="documents/stored-budget.txt")
        database.claim_document_for_processing.return_value = True
        s3_client.fetch_object.side_effect = RuntimeError("S3 unavailable")

        with self.assertRaisesRegex(RuntimeError, "S3 unavailable"):
            self._process_message(
                logger,
                database,
                sqs_client,
                s3_client,
                embedder,
                {"ReceiptHandle": "receipt-1", "Body": '{"document_id":"doc-1","key":"documents/payload-budget.txt"}'},
            )

        database.update_document_status.assert_called_with("doc-1", "failed")
        sqs_client.delete_message.assert_called_once_with("receipt-1")


if __name__ == "__main__":
    unittest.main()
