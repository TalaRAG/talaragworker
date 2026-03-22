from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import logging

from talaragworker.config import Settings


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_index: int
    content: str
    embedding: list[float]


class DocumentEmbedder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_backend = "openai" if settings.use_openai else "llama_cpp"

        if settings.use_openai:
            openai_module = import_module("openai")
            self._client = openai_module.OpenAI()
        else:
            llama_cpp_module = import_module("llama_cpp")
            self._client = llama_cpp_module.Llama(
                model_path=settings.llm_model,
                embedding=True,
                verbose=False,
            )

    def embed_document(
        self,
        content: str,
        *,
        logger: logging.Logger | None = None,
        document_id: str | None = None,
    ) -> list[EmbeddedChunk]:
        chunks = self._chunk_text(content)
        embedded_chunks: list[EmbeddedChunk] = []
        total_chunks = len(chunks)

        for chunk_index, chunk in enumerate(chunks):
            if logger is not None:
                logger.info(
                    "Embedding chunk %s/%s for document_id=%s",
                    chunk_index + 1,
                    total_chunks,
                    document_id or "unknown",
                )
            embedding = self._create_embedding(chunk)
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk_index=chunk_index,
                    content=chunk,
                    embedding=embedding,
                )
            )

        return embedded_chunks

    def _chunk_text(self, content: str) -> list[str]:
        normalized = " ".join(content.split())
        if not normalized:
            return []

        chunk_size = self._settings.embedding_chunk_size
        overlap = self._settings.embedding_chunk_overlap
        step = chunk_size - overlap

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = start + chunk_size
            chunks.append(normalized[start:end])
            start += step

        return chunks

    def _create_embedding(self, chunk: str) -> list[float]:
        if self._embedding_backend == "openai":
            response = self._client.embeddings.create(
                model=self._settings.openai_embedding_model,
                input=chunk,
            )
            return response.data[0].embedding

        response = self._client.create_embedding(chunk)
        return response["data"][0]["embedding"]
