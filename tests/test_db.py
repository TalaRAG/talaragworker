import sys
import unittest
from datetime import datetime
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID


class FakeComposable:
    def __init__(self, template: str = "") -> None:
        self.template = template

    def format(self, **_kwargs):
        return self

    def join(self, _items):
        return self


class FakeSQLModule:
    @staticmethod
    def SQL(template: str) -> FakeComposable:
        return FakeComposable(template)

    @staticmethod
    def Identifier(_name: str) -> FakeComposable:
        return FakeComposable()


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.cursor.__enter__.return_value = self.cursor
        self.cursor.__exit__.return_value = None
        self.connection.cursor.return_value = self.cursor

        fake_psycopg = SimpleNamespace(
            connect=MagicMock(return_value=self.connection),
            Cursor=object,
            sql=FakeSQLModule(),
        )
        fake_rows = SimpleNamespace(dict_row=MagicMock())
        fake_json = SimpleNamespace(Json=MagicMock(side_effect=lambda value: value))

        self.module_patcher = patch.dict(
            sys.modules,
            {
                "psycopg": fake_psycopg,
                "psycopg.sql": fake_psycopg.sql,
                "psycopg.rows": fake_rows,
                "psycopg.types": SimpleNamespace(json=fake_json),
                "psycopg.types.json": fake_json,
            },
        )
        self.module_patcher.start()
        sys.modules.pop("talaragworker.db", None)
        db_module = import_module("talaragworker.db")
        embedder_module = import_module("talaragworker.embedder")
        self.Database = db_module.Database
        self.EmbeddedChunk = embedder_module.EmbeddedChunk

    def tearDown(self) -> None:
        self.module_patcher.stop()
        sys.modules.pop("talaragworker.db", None)

    def test_replace_document_embeddings_populates_required_metadata_columns(self) -> None:
        self.cursor.fetchall.return_value = [
            {"column_name": "id"},
            {"column_name": "document_id"},
            {"column_name": "chunk_index"},
            {"column_name": "content"},
            {"column_name": "embedding"},
            {"column_name": "embedding_model"},
            {"column_name": "dimensions"},
            {"column_name": "created_at"},
            {"column_name": "updated_at"},
        ]
        settings = SimpleNamespace(
            db_host="localhost",
            db_port=5432,
            db_username="postgres",
            db_password="postgres",
            db_name="talaragapi_development",
            document_embeddings_table="document_embeddings",
            document_embeddings_document_id_column="document_id",
            document_embeddings_chunk_index_column="chunk_index",
            document_embeddings_content_column="content",
            document_embeddings_vector_column="embedding",
            embedding_storage_format="vector",
            use_openai=True,
            openai_embedding_model="text-embedding-3-large",
            llm_model=None,
        )
        database = self.Database(settings)

        database.replace_document_embeddings(
            "doc-1",
            [
                self.EmbeddedChunk(
                    chunk_index=0,
                    content="hello world",
                    embedding=[0.1, 0.2],
                )
            ],
        )

        insert_params = self.cursor.execute.call_args_list[2].args[1]
        self.assertEqual(insert_params[0], "doc-1")
        self.assertEqual(insert_params[1], 0)
        self.assertEqual(insert_params[2], "hello world")
        self.assertEqual(insert_params[3], "[0.1,0.2]")
        self.assertEqual(insert_params[5], "text-embedding-3-large")
        self.assertEqual(insert_params[6], 2)
        self.assertIsInstance(insert_params[7], datetime)
        self.assertIsInstance(insert_params[8], datetime)
        UUID(insert_params[4])
        self.connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
