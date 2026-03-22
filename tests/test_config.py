import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from talaragworker.config import load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_load_settings_includes_sqs_visibility_configuration(self) -> None:
        env = {
            "SQS_QUEUE": "https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
            "S3_BUCKET_NAME": "bucket",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_USERNAME": "postgres",
            "DB_PASSWORD": "postgres",
            "LLM_MODEL": "/tmp/model.gguf",
            "SQS_VISIBILITY_TIMEOUT_SECONDS": "1800",
            "SQS_VISIBILITY_HEARTBEAT_SECONDS": "120",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = load_settings()

        self.assertEqual(settings.sqs_visibility_timeout_seconds, 1800)
        self.assertEqual(settings.sqs_visibility_heartbeat_seconds, 120)

    def test_load_settings_rejects_heartbeat_not_smaller_than_visibility_timeout(self) -> None:
        env = {
            "SQS_QUEUE": "https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
            "S3_BUCKET_NAME": "bucket",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DB_USERNAME": "postgres",
            "DB_PASSWORD": "postgres",
            "LLM_MODEL": "/tmp/model.gguf",
            "SQS_VISIBILITY_TIMEOUT_SECONDS": "300",
            "SQS_VISIBILITY_HEARTBEAT_SECONDS": "300",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(
                ValueError,
                "SQS_VISIBILITY_HEARTBEAT_SECONDS must be smaller than SQS_VISIBILITY_TIMEOUT_SECONDS",
            ):
                load_settings()

    def test_load_settings_reads_values_from_dotenv_in_current_directory(self) -> None:
        dotenv = "\n".join(
            [
                "SQS_QUEUE=https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
                "S3_BUCKET_NAME=bucket",
                "DB_HOST=localhost",
                "DB_PORT=5432",
                "DB_USERNAME=postgres",
                "DB_PASSWORD=postgres",
                "LLM_MODEL=/tmp/model.gguf",
                "",
            ]
        )

        previous_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(dotenv, encoding="utf-8")

            os.chdir(temp_dir)
            try:
                with patch.dict(os.environ, {}, clear=True):
                    settings = load_settings()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(
            settings.sqs_queue,
            "https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo",
        )
        self.assertEqual(settings.s3_bucket_name, "bucket")


if __name__ == "__main__":
    unittest.main()
