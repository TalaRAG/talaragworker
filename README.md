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

Update `.env` with your queue, database, and model path values.

The worker reads configuration from process environment variables. Before running it, load `.env` into your shell:

```bash
set -a
source .env
set +a
```

## Run

```bash
python -m talaragworker
```

## Environment variables

Copy values from `.env.example`. Required settings are:

```bash
SQS_QUEUE=https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue
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

`DOCUMENT_S3_KEY_COLUMN` is the column on `DOCUMENTS_TABLE` that stores the S3 object key for the source file. `DOCUMENT_EMBEDDINGS_CONTENT_COLUMN` controls which column on `DOCUMENT_EMBEDDINGS_TABLE` stores each embedded chunk's text.

By default the worker writes embeddings as `pgvector` values using `EMBEDDING_STORAGE_FORMAT=vector`. Set `EMBEDDING_STORAGE_FORMAT=json` if the embeddings column stores JSON instead.
