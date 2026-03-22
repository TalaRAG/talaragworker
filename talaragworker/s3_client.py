from __future__ import annotations

import boto3

from talaragworker.config import Settings


class S3Client:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client("s3", region_name=settings.aws_region)
        self._bucket_name = settings.s3_bucket_name
        self.ensure_bucket_is_reachable()

    def ensure_bucket_is_reachable(self) -> None:
        self._client.head_bucket(Bucket=self._bucket_name)

    def fetch_text(self, object_key: str) -> str:
        response = self._client.get_object(Bucket=self._bucket_name, Key=object_key)
        body = response["Body"].read()
        return body.decode("utf-8")
