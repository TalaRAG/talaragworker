# Instructions

## Syntax

```bash
python -m talaragworker
```

## Process

1. Run through a loop every 3 seconds and poll the FIFO `SQS_QUEUE` for a payload
2. Download the file from S3 as defined in `S3_BUCKET_NAME`
3. Create the embeddings and store in `document_embeddings` 
4. Refresh the SQS visibility timeout while processing so long-running embeds do not requeue mid-flight
5. Update status of document as defined by `document_id` to `done`

## Structure

Payload structure from SQS is defined as follows:

```json
{
    "document_id": "abcdefg12345",
    "key": "some_key"
}
```
