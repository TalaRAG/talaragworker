import sys
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class S3ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.boto_client = MagicMock()
        self.boto3_module = SimpleNamespace(client=MagicMock(return_value=self.boto_client))
        self.module_patcher = patch.dict(sys.modules, {"boto3": self.boto3_module})
        self.module_patcher.start()
        sys.modules.pop("talaragworker.s3_client", None)
        self.s3_client_module = import_module("talaragworker.s3_client")
        self.S3Client = self.s3_client_module.S3Client

        self.settings = SimpleNamespace(
            aws_region="ap-southeast-1",
            s3_bucket_name="my-document-bucket",
        )

    def tearDown(self) -> None:
        self.module_patcher.stop()
        sys.modules.pop("talaragworker.s3_client", None)

    def test_init_checks_bucket_reachability(self) -> None:
        client = self.S3Client(self.settings)

        self.assertIsNotNone(client)
        self.boto_client.head_bucket.assert_called_once_with(Bucket=self.settings.s3_bucket_name)

    def test_fetch_text_reads_object_from_configured_bucket(self) -> None:
        self.boto_client.get_object.return_value = {"Body": SimpleNamespace(read=lambda: b"hello")}

        client = self.S3Client(self.settings)
        text = client.fetch_text("path/to/file.txt")

        self.assertEqual(text, "hello")
        self.boto_client.get_object.assert_called_once_with(
            Bucket=self.settings.s3_bucket_name,
            Key="path/to/file.txt",
        )


if __name__ == "__main__":
    unittest.main()
