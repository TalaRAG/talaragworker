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
        worker_module = import_module("talaragworker.worker")
        self._process_message = worker_module._process_message
        self._log_runtime_targets = worker_module._log_runtime_targets
        self._log_expected_environment = worker_module._log_expected_environment

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

    def test_startup_logging_includes_runtime_targets_and_expected_environment(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        settings = SimpleNamespace(
            app_env="production",
            aws_region="ap-southeast-1",
            sqs_queue="https://sqs.ap-southeast-1.amazonaws.com/123456789012/talarag-prod.fifo",
            s3_bucket_name="talarag-prod-documents",
            db_host="db.internal",
            db_port=5432,
            db_name="talaragapi_production",
            db_username="talarag",
            documents_table="documents",
            document_id_column="id",
            document_s3_key_column="storage_key",
            document_status_column="status",
            poll_interval_seconds=5,
            sqs_wait_time_seconds=20,
            use_openai=True,
            openai_embedding_model="text-embedding-3-large",
            llm_model=None,
        )

        self._log_runtime_targets(logger, settings)
        self._log_expected_environment(logger, settings)

        logger.info.assert_any_call(
            "Worker targets: app_env=%s aws_region=%s sqs_queue=%s s3_bucket=%s db_host=%s db_port=%s db_name=%s documents_table=%s document_id_column=%s document_s3_key_column=%s",
            "production",
            "ap-southeast-1",
            "https://sqs.ap-southeast-1.amazonaws.com/123456789012/talarag-prod.fifo",
            "talarag-prod-documents",
            "db.internal",
            5432,
            "talaragapi_production",
            "documents",
            "id",
            "storage_key",
        )
        logger.info.assert_any_call("Expected worker environment:")
        logger.info.assert_any_call("  %s=%s", "DB_NAME", "talaragapi_production")
        logger.info.assert_any_call(
            "  %s=%s",
            "SQS_QUEUE",
            "https://sqs.ap-southeast-1.amazonaws.com/123456789012/talarag-prod.fifo",
        )
        logger.info.assert_any_call("  %s=%s", "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")


if __name__ == "__main__":
    unittest.main()
