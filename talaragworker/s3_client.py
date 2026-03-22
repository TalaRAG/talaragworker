from __future__ import annotations

from dataclasses import dataclass

import boto3

from talaragworker.config import Settings


@dataclass(frozen=True)
class S3Object:
    body: bytes
    content_type: str | None


class S3Client:
    def __init__(self, settings: Settings) -> None:
        self._client = boto3.client("s3", region_name=settings.aws_region)
        self._bucket_name = settings.s3_bucket_name
        self.ensure_bucket_is_reachable()

    def ensure_bucket_is_reachable(self) -> None:
        self._client.head_bucket(Bucket=self._bucket_name)

    def fetch_object(self, object_key: str) -> S3Object:
        response = self._client.get_object(Bucket=self._bucket_name, Key=object_key)
        return S3Object(
            body=response["Body"].read(),
            content_type=response.get("ContentType"),
        )
