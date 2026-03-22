from __future__ import annotations

import os
from dataclasses import dataclass

from talaragworker.env import load_dotenv_if_present


def _get_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    app_env: str
    aws_region: str
    sqs_queue: str
    sqs_visibility_timeout_seconds: int
    sqs_visibility_heartbeat_seconds: int
    s3_bucket_name: str
    db_host: str
    db_port: int
    db_username: str
    db_password: str
    db_name: str
    use_openai: bool
    llm_model: str | None
    openai_embedding_model: str | None
    poll_interval_seconds: int
    sqs_wait_time_seconds: int
    documents_table: str
    document_id_column: str
    document_s3_key_column: str
    document_status_column: str
    document_embeddings_table: str
    document_embeddings_document_id_column: str
    document_embeddings_chunk_index_column: str
    document_embeddings_content_column: str
    document_embeddings_vector_column: str
    embedding_storage_format: str
    embedding_chunk_size: int
    embedding_chunk_overlap: int


def load_settings() -> Settings:
    load_dotenv_if_present()

    use_openai = _get_bool("USE_OPENAI", False)
    embedding_storage_format = os.getenv("EMBEDDING_STORAGE_FORMAT", "vector").strip().lower()
    if embedding_storage_format not in {"vector", "json"}:
        raise ValueError("EMBEDDING_STORAGE_FORMAT must be either 'vector' or 'json'")

    chunk_size = _get_int("EMBEDDING_CHUNK_SIZE", 1000)
    chunk_overlap = _get_int("EMBEDDING_CHUNK_OVERLAP", 200)
    if chunk_size <= 0:
        raise ValueError("EMBEDDING_CHUNK_SIZE must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("EMBEDDING_CHUNK_OVERLAP must be 0 or greater")
    if chunk_overlap >= chunk_size:
        raise ValueError("EMBEDDING_CHUNK_OVERLAP must be smaller than EMBEDDING_CHUNK_SIZE")

    sqs_visibility_timeout_seconds = _get_int("SQS_VISIBILITY_TIMEOUT_SECONDS", 3600)
    sqs_visibility_heartbeat_seconds = _get_int("SQS_VISIBILITY_HEARTBEAT_SECONDS", 300)
    if sqs_visibility_timeout_seconds <= 0:
        raise ValueError("SQS_VISIBILITY_TIMEOUT_SECONDS must be greater than 0")
    if sqs_visibility_timeout_seconds > 43200:
        raise ValueError("SQS_VISIBILITY_TIMEOUT_SECONDS must be 43200 seconds or less")
    if sqs_visibility_heartbeat_seconds <= 0:
        raise ValueError("SQS_VISIBILITY_HEARTBEAT_SECONDS must be greater than 0")
    if sqs_visibility_heartbeat_seconds >= sqs_visibility_timeout_seconds:
        raise ValueError(
            "SQS_VISIBILITY_HEARTBEAT_SECONDS must be smaller than SQS_VISIBILITY_TIMEOUT_SECONDS"
        )

    llm_model = (os.getenv("LLM_MODEL") or "").strip() or None
    openai_embedding_model = (os.getenv("OPENAI_EMBEDDING_MODEL") or "").strip() or None
    if use_openai:
        if not openai_embedding_model:
            raise ValueError("Missing required environment variable: OPENAI_EMBEDDING_MODEL")
    elif not llm_model:
        raise ValueError("Missing required environment variable: LLM_MODEL")

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        aws_region=os.getenv("AWS_REGION", "ap-southeast-1"),
        sqs_queue=_get_required("SQS_QUEUE"),
        sqs_visibility_timeout_seconds=sqs_visibility_timeout_seconds,
        sqs_visibility_heartbeat_seconds=sqs_visibility_heartbeat_seconds,
        s3_bucket_name=_get_required("S3_BUCKET_NAME"),
        db_host=_get_required("DB_HOST"),
        db_port=_get_int("DB_PORT", 5432),
        db_username=_get_required("DB_USERNAME"),
        db_password=_get_required("DB_PASSWORD"),
        db_name=os.getenv("DB_NAME", "talaragapi_development"),
        use_openai=use_openai,
        llm_model=llm_model,
        openai_embedding_model=openai_embedding_model,
        poll_interval_seconds=_get_int("POLL_INTERVAL_SECONDS", 5),
        sqs_wait_time_seconds=_get_int("SQS_WAIT_TIME_SECONDS", 20),
        documents_table=os.getenv("DOCUMENTS_TABLE", "documents"),
        document_id_column=os.getenv("DOCUMENT_ID_COLUMN", "id"),
        document_s3_key_column=os.getenv("DOCUMENT_S3_KEY_COLUMN", os.getenv("DOCUMENT_CONTENT_COLUMN", "storage_key")),
        document_status_column=os.getenv("DOCUMENT_STATUS_COLUMN", "status"),
        document_embeddings_table=os.getenv("DOCUMENT_EMBEDDINGS_TABLE", "document_embeddings"),
        document_embeddings_document_id_column=os.getenv("DOCUMENT_EMBEDDINGS_DOCUMENT_ID_COLUMN", "document_id"),
        document_embeddings_chunk_index_column=os.getenv("DOCUMENT_EMBEDDINGS_CHUNK_INDEX_COLUMN", "chunk_index"),
        document_embeddings_content_column=os.getenv("DOCUMENT_EMBEDDINGS_CONTENT_COLUMN", "content"),
        document_embeddings_vector_column=os.getenv("DOCUMENT_EMBEDDINGS_VECTOR_COLUMN", "embedding"),
        embedding_storage_format=embedding_storage_format,
        embedding_chunk_size=chunk_size,
        embedding_chunk_overlap=chunk_overlap,
    )


REQUIRED_ENVIRONMENT_VARIABLES = (
    "SQS_QUEUE",
    "S3_BUCKET_NAME",
    "DB_HOST",
    "DB_USERNAME",
    "DB_PASSWORD",
)
