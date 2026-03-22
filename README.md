# talaragworker

Local SQS worker that loads document metadata from PostgreSQL, fetches file content from S3, generates embeddings with `llama-cpp-python`, and stores them in a `pgvector` column on `document_embeddings`.

## Install

```bash
python -m pip install -e .
```

## Configure environment

```bash
cp .env.example .env
```

Update `.env` with your queue, bucket, and database values.

The worker reads configuration from process environment variables and automatically loads a `.env` file from the current working directory (or its parents) when present. Exporting values in your shell still works and takes precedence over `.env`.

Validate your environment before starting the worker:

```bash
python -m talaragworker --mode doctor
```

## Run

```bash
python -m talaragworker
```

## Environment variables

Copy values from `.env.example`. Required settings are:

```bash
SQS_QUEUE=https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue.fifo
S3_BUCKET_NAME=my-document-bucket
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USERNAME=postgres
DB_PASSWORD=postgres
LLM_MODEL=/absolute/path/to/embedding-model.gguf
```

Optional settings and defaults are:

```bash
APP_ENV=development
AWS_REGION=ap-southeast-1
DB_NAME=postgres
POLL_INTERVAL_SECONDS=5
SQS_WAIT_TIME_SECONDS=20
SQS_VISIBILITY_TIMEOUT_SECONDS=3600
SQS_VISIBILITY_HEARTBEAT_SECONDS=300
DOCUMENTS_TABLE=documents
DOCUMENT_ID_COLUMN=id
DOCUMENT_S3_KEY_COLUMN=content
DOCUMENT_STATUS_COLUMN=status
DOCUMENT_EMBEDDINGS_TABLE=document_embeddings
DOCUMENT_EMBEDDINGS_DOCUMENT_ID_COLUMN=document_id
DOCUMENT_EMBEDDINGS_CHUNK_INDEX_COLUMN=chunk_index
DOCUMENT_EMBEDDINGS_CONTENT_COLUMN=content
DOCUMENT_EMBEDDINGS_VECTOR_COLUMN=embedding
EMBEDDING_STORAGE_FORMAT=vector
EMBEDDING_CHUNK_SIZE=1000
EMBEDDING_CHUNK_OVERLAP=200
```

`python -m talaragworker --mode doctor` checks that required environment variables are present, that numeric and enum settings pass the same validation rules used by the worker, that `SQS_QUEUE` resolves to a reachable FIFO queue, that `S3_BUCKET_NAME` is reachable, and that `LLM_MODEL` points to an existing file.

`DOCUMENT_S3_KEY_COLUMN` is the column on `DOCUMENTS_TABLE` that stores the S3 object key for the source file. `DOCUMENT_EMBEDDINGS_CONTENT_COLUMN` controls which column on `DOCUMENT_EMBEDDINGS_TABLE` stores each embedded chunk's text.

The worker validates that `SQS_QUEUE` resolves to an actual FIFO queue and will refuse to start against a standard queue.

By default the worker writes embeddings as `pgvector` values using `EMBEDDING_STORAGE_FORMAT=vector`. Set `EMBEDDING_STORAGE_FORMAT=json` if the embeddings column stores JSON instead.

The worker receives each message with a 1-hour visibility lease by default and refreshes that lease every 5 minutes while a document is still being embedded. Increase `SQS_VISIBILITY_TIMEOUT_SECONDS` if a single embedding run can exceed that initial lease.
