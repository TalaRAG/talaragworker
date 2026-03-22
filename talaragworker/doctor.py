from __future__ import annotations

import os
import sys
from pathlib import Path

from talaragworker.config import REQUIRED_ENVIRONMENT_VARIABLES, load_settings
from talaragworker.env import load_dotenv_if_present
from talaragworker.s3_client import S3Client
from talaragworker.sqs_client import SQSClient


def doctor() -> int:
    load_dotenv_if_present()

    missing_variables = [name for name in REQUIRED_ENVIRONMENT_VARIABLES if not (os.getenv(name) or "").strip()]
    if missing_variables:
        for name in missing_variables:
            print(f"Missing required environment variable: {name}", file=sys.stderr)
        return 1

    try:
        settings = load_settings()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not Path(settings.llm_model).exists():
        print(f"LLM_MODEL path does not exist: {settings.llm_model}", file=sys.stderr)
        return 1

    try:
        SQSClient(settings)
    except Exception as exc:
        print(f"SQS_QUEUE is not reachable or is not FIFO: {exc}", file=sys.stderr)
        return 1

    try:
        S3Client(settings)
    except Exception as exc:
        print(f"S3_BUCKET_NAME is not reachable: {exc}", file=sys.stderr)
        return 1

    print("Environment configuration is valid.")
    return 0
