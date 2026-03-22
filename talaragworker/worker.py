from __future__ import annotations

import json
import logging
import time
from typing import Any

from talaragworker.config import Settings, load_settings
from talaragworker.db import Database
from talaragworker.document_extractor import extract_text
from talaragworker.embedder import DocumentEmbedder
from talaragworker.logging_config import configure_logging
from talaragworker.s3_client import S3Client
from talaragworker.sqs_client import SQSClient


def run() -> None:
    settings = load_settings()
    logger = configure_logging(settings.app_env)
    logger.info("Starting talaragworker")
    logger.info(
        "Embedding backend configured as %s",
        "openai" if settings.use_openai else "local",
    )

    database = Database(settings)
    sqs_client = SQSClient(settings)
    s3_client = S3Client(settings)
    embedder = DocumentEmbedder(settings)

    try:
        _run_loop(settings, logger, database, sqs_client, s3_client, embedder)
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down")
    finally:
        database.close()
        logger.info("Worker stopped")


def _run_loop(
    settings: Settings,
    logger: logging.Logger,
    database: Database,
    sqs_client: SQSClient,
    s3_client: S3Client,
    embedder: DocumentEmbedder,
) -> None:
    while True:
        message = sqs_client.receive_message()
        if message is None:
            logger.info("No messages in queue")
            time.sleep(settings.poll_interval_seconds)
            continue

        try:
            _process_message(logger, database, sqs_client, s3_client, embedder, message)
        except Exception:
            logger.exception("Message processing failed and the worker will continue")


def _process_message(
    logger: logging.Logger,
    database: Database,
    sqs_client: SQSClient,
    s3_client: S3Client,
    embedder: DocumentEmbedder,
    message: dict[str, Any],
) -> None:
    receipt_handle = message["ReceiptHandle"]
    body = message.get("Body", "")

    logger.info("Received SQS message")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.exception("Failed to decode SQS message body as JSON")
        sqs_client.delete_message(receipt_handle)
        logger.info("Deleted invalid SQS message")
        raise RuntimeError("Invalid SQS message body") from exc

    document_id = payload.get("document_id")
    if document_id is None:
        sqs_client.delete_message(receipt_handle)
        logger.info("Deleted SQS message with missing document_id")
        raise RuntimeError("SQS message is missing document_id")
    key = payload.get("key")
    if not key:
        sqs_client.delete_message(receipt_handle)
        logger.info("Deleted SQS message with missing key for document_id=%s", document_id)
        raise RuntimeError("SQS message is missing key")

    logger.info("Fetching document_id=%s", document_id)
    document = database.fetch_document(document_id)
    if document is None:
        sqs_client.delete_message(receipt_handle)
        logger.info("Deleted SQS message for missing document_id=%s", document_id)
        raise RuntimeError(f"Document not found for document_id={document_id}")

    try:
        with sqs_client.lease_message(receipt_handle, logger):
            claimed = database.claim_document_for_processing(document_id)
            if not claimed:
                logger.info(
                    "Skipped document_id=%s because it is already being processed or is no longer pending",
                    document_id,
                )
                sqs_client.delete_message(receipt_handle)
                logger.info("Deleted duplicate SQS message for document_id=%s", document_id)
                return

            logger.info("Processing document_id=%s", document_id)
            logger.info("Updated document_id=%s status to processing", document_id)

            if document.s3_key and document.s3_key != key:
                logger.warning(
                    "Payload key does not match stored key for document_id=%s payload_key=%s stored_key=%s",
                    document_id,
                    key,
                    document.s3_key,
                )

            logger.info("Fetching S3 object for document_id=%s key=%s", document_id, key)
            s3_object = s3_client.fetch_object(key)
            logger.info("Fetched S3 object for document_id=%s", document_id)

            content = extract_text(key, s3_object.content_type, s3_object.body)
            logger.info("Extracted text for document_id=%s", document_id)

            chunks = embedder.embed_document(content, logger=logger, document_id=str(document_id))
            logger.info("Generated %s embedding chunk(s) for document_id=%s", len(chunks), document_id)

            database.replace_document_embeddings(document_id, chunks)
            logger.info("Inserted embeddings for document_id=%s", document_id)

            database.update_document_status(document_id, "done")
            logger.info("Updated document_id=%s status to done", document_id)

            sqs_client.delete_message(receipt_handle)
            logger.info("Deleted SQS message for document_id=%s", document_id)
    except Exception:
        _mark_failed(logger, database, document_id)
        try:
            sqs_client.delete_message(receipt_handle)
            logger.info("Deleted failed SQS message for document_id=%s", document_id)
        except Exception:
            logger.exception("Failed to delete failed SQS message for document_id=%s", document_id)
        logger.exception("Failed to process document_id=%s", document_id)
        raise


def _mark_failed(logger: logging.Logger, database: Database, document_id: Any) -> None:
    try:
        database.update_document_status(document_id, "failed")
        logger.info("Updated document_id=%s status to failed", document_id)
    except Exception:
        logger.exception("Failed to update document_id=%s status to failed", document_id)
