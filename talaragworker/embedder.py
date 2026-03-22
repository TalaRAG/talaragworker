from __future__ import annotations

from dataclasses import dataclass

from llama_cpp import Llama

from talaragworker.config import Settings


@dataclass(frozen=True)
class EmbeddedChunk:
    chunk_index: int
    content: str
    embedding: list[float]


class DocumentEmbedder:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._llm = Llama(model_path=settings.llm_model, embedding=True, verbose=False)

    def embed_document(self, content: str) -> list[EmbeddedChunk]:
        chunks = self._chunk_text(content)
        embedded_chunks: list[EmbeddedChunk] = []

        for chunk_index, chunk in enumerate(chunks):
            response = self._llm.create_embedding(chunk)
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk_index=chunk_index,
                    content=chunk,
                    embedding=response["data"][0]["embedding"],
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
