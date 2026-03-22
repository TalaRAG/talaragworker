# talaragworker

Local SQS worker that loads documents from PostgreSQL, generates embeddings with `llama-cpp-python`, and stores them in a `pgvector` column on `document_embeddings`.

## Install

```bash
python -m pip install -e .
```

## Run

```bash
python -m talaragworker
```

## Required environment variables

```bash
export AWS_REGION=ap-southeast-1
export SQS_QUEUE=https://sqs.ap-southeast-1.amazonaws.com/123456789012/my-queue
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_USERNAME=postgres
export DB_PASSWORD=postgres
export DB_NAME=postgres
export LLM_MODEL=/absolute/path/to/embedding-model.gguf
```

## Optional environment variables

```bash
export APP_ENV=development
export POLL_INTERVAL_SECONDS=5
export SQS_WAIT_TIME_SECONDS=20
export DOCUMENTS_TABLE=documents
export DOCUMENT_ID_COLUMN=id
export DOCUMENT_CONTENT_COLUMN=content
export DOCUMENT_STATUS_COLUMN=status
export DOCUMENT_EMBEDDINGS_TABLE=document_embeddings
export DOCUMENT_EMBEDDINGS_DOCUMENT_ID_COLUMN=document_id
export DOCUMENT_EMBEDDINGS_CHUNK_INDEX_COLUMN=chunk_index
export DOCUMENT_EMBEDDINGS_CONTENT_COLUMN=content
export DOCUMENT_EMBEDDINGS_VECTOR_COLUMN=embedding
export EMBEDDING_STORAGE_FORMAT=vector
export EMBEDDING_CHUNK_SIZE=1000
export EMBEDDING_CHUNK_OVERLAP=200
```

By default the worker writes embeddings as `pgvector` values using `EMBEDDING_STORAGE_FORMAT=vector`.
