import logging
import sys
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class DocumentEmbedderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.llama_instance = MagicMock()
        self.llama_instance.create_embedding.side_effect = [
            {"data": [{"embedding": [0.1, 0.2]}]},
            {"data": [{"embedding": [0.3, 0.4]}]},
        ]
        self.openai_client = MagicMock()
        self.openai_client.embeddings.create.side_effect = [
            SimpleNamespace(data=[SimpleNamespace(embedding=[0.5, 0.6])]),
            SimpleNamespace(data=[SimpleNamespace(embedding=[0.7, 0.8])]),
        ]
        self.module_patcher = patch.dict(
            sys.modules,
            {
                "llama_cpp": SimpleNamespace(Llama=MagicMock(return_value=self.llama_instance)),
                "openai": SimpleNamespace(OpenAI=MagicMock(return_value=self.openai_client)),
            },
        )
        self.module_patcher.start()
        sys.modules.pop("talaragworker.embedder", None)
        self.embedder_module = import_module("talaragworker.embedder")
        self.DocumentEmbedder = self.embedder_module.DocumentEmbedder

        self.local_settings = SimpleNamespace(
            llm_model="/tmp/model.gguf",
            openai_embedding_model=None,
            use_openai=False,
            embedding_chunk_size=6,
            embedding_chunk_overlap=0,
        )
        self.openai_settings = SimpleNamespace(
            llm_model=None,
            openai_embedding_model="text-embedding-3-large",
            use_openai=True,
            embedding_chunk_size=6,
            embedding_chunk_overlap=0,
        )

    def tearDown(self) -> None:
        self.module_patcher.stop()
        sys.modules.pop("talaragworker.embedder", None)

    def test_embed_document_logs_chunk_progress(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        embedder = self.DocumentEmbedder(self.local_settings)

        chunks = embedder.embed_document("hello world", logger=logger, document_id="doc-1")

        self.assertEqual(len(chunks), 2)
        logger.info.assert_any_call("Embedding chunk %s/%s for document_id=%s", 1, 2, "doc-1")
        logger.info.assert_any_call("Embedding chunk %s/%s for document_id=%s", 2, 2, "doc-1")

    def test_embed_document_uses_openai_when_enabled(self) -> None:
        embedder = self.DocumentEmbedder(self.openai_settings)

        chunks = embedder.embed_document("hello world")

        self.assertEqual([chunk.embedding for chunk in chunks], [[0.5, 0.6], [0.7, 0.8]])
        self.openai_client.embeddings.create.assert_any_call(
            model="text-embedding-3-large",
            input="hello ",
        )
        self.openai_client.embeddings.create.assert_any_call(
            model="text-embedding-3-large",
            input="world",
        )


if __name__ == "__main__":
    unittest.main()
