from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Json

from talaragworker.config import Settings
from talaragworker.embedder import EmbeddedChunk


@dataclass(frozen=True)
class DocumentRecord:
    document_id: Any
    s3_key: str


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._embedding_table_columns: set[str] | None = None
        self._connection = psycopg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            dbname=settings.db_name,
            row_factory=dict_row,
        )
        self._connection.autocommit = False

    def close(self) -> None:
        self._connection.close()

    def fetch_document(self, document_id: Any) -> DocumentRecord | None:
        query = sql.SQL(
            """
            SELECT {id_column}, {s3_key_column}
            FROM {documents_table}
            WHERE {id_column} = %s
            LIMIT 1
            """
        ).format(
            id_column=sql.Identifier(self._settings.document_id_column),
            s3_key_column=sql.Identifier(self._settings.document_s3_key_column),
            documents_table=sql.Identifier(self._settings.documents_table),
        )

        with self._connection.cursor() as cursor:
            cursor.execute(query, (document_id,))
            row = cursor.fetchone()

        if row is None:
            self._connection.rollback()
            return None

        self._connection.rollback()
        s3_key = row.get(self._settings.document_s3_key_column)
        return DocumentRecord(document_id=row[self._settings.document_id_column], s3_key=s3_key or "")

    def update_document_status(self, document_id: Any, status: str) -> None:
        query = sql.SQL(
            """
            UPDATE {documents_table}
            SET {status_column} = %s
            WHERE {id_column} = %s
            """
        ).format(
            documents_table=sql.Identifier(self._settings.documents_table),
            status_column=sql.Identifier(self._settings.document_status_column),
            id_column=sql.Identifier(self._settings.document_id_column),
        )

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query, (status, document_id))
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def claim_document_for_processing(self, document_id: Any) -> bool:
        query = sql.SQL(
            """
            UPDATE {documents_table}
            SET {status_column} = %s
            WHERE {id_column} = %s
              AND {status_column} = %s
            """
        ).format(
            documents_table=sql.Identifier(self._settings.documents_table),
            status_column=sql.Identifier(self._settings.document_status_column),
            id_column=sql.Identifier(self._settings.document_id_column),
        )

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(query, ("processing", document_id, "pending"))
                claimed = cursor.rowcount == 1
            self._connection.commit()
            return claimed
        except Exception:
            self._connection.rollback()
            raise

    def replace_document_embeddings(self, document_id: Any, chunks: list[EmbeddedChunk]) -> None:
        delete_query = sql.SQL(
            """
            DELETE FROM {embeddings_table}
            WHERE {document_id_column} = %s
            """
        ).format(
            embeddings_table=sql.Identifier(self._settings.document_embeddings_table),
            document_id_column=sql.Identifier(self._settings.document_embeddings_document_id_column),
        )

        vector_value = sql.SQL("%s")
        if self._settings.embedding_storage_format == "vector":
            vector_value = sql.SQL("CAST(%s AS vector)")

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(delete_query, (document_id,))
                embedding_table_columns = self._get_embedding_table_columns(cursor)
                for chunk in chunks:
                    insert_query, params = self._build_embedding_insert(
                        document_id,
                        chunk,
                        embedding_table_columns,
                        vector_value,
                    )
                    cursor.execute(
                        insert_query,
                        params,
                    )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def _get_embedding_table_columns(self, cursor: psycopg.Cursor[Any]) -> set[str]:
        if self._embedding_table_columns is not None:
            return self._embedding_table_columns

        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            """,
            (self._settings.document_embeddings_table,),
        )
        self._embedding_table_columns = {row["column_name"] for row in cursor.fetchall()}
        return self._embedding_table_columns

    def _build_embedding_insert(
        self,
        document_id: Any,
        chunk: EmbeddedChunk,
        embedding_table_columns: set[str],
        vector_value: sql.SQL,
    ) -> tuple[sql.SQL, tuple[Any, ...]]:
        column_identifiers: list[sql.Composable] = [
            sql.Identifier(self._settings.document_embeddings_document_id_column),
            sql.Identifier(self._settings.document_embeddings_chunk_index_column),
            sql.Identifier(self._settings.document_embeddings_content_column),
            sql.Identifier(self._settings.document_embeddings_vector_column),
        ]
        value_identifiers: list[sql.Composable] = [
            sql.SQL("%s"),
            sql.SQL("%s"),
            sql.SQL("%s"),
            vector_value,
        ]
        params: list[Any] = [
            document_id,
            chunk.chunk_index,
            chunk.content,
            self._serialize_embedding(chunk.embedding),
        ]

        now = datetime.now(timezone.utc)
        optional_metadata = (
            ("id", str(uuid4())),
            ("embedding_model", self._embedding_model_name()),
            ("dimensions", len(chunk.embedding)),
            ("created_at", now),
            ("updated_at", now),
        )
        for column_name, value in optional_metadata:
            if column_name not in embedding_table_columns:
                continue
            column_identifiers.append(sql.Identifier(column_name))
            value_identifiers.append(sql.SQL("%s"))
            params.append(value)

        insert_query = sql.SQL(
            """
            INSERT INTO {embeddings_table} ({columns})
            VALUES ({values})
            """
        ).format(
            embeddings_table=sql.Identifier(self._settings.document_embeddings_table),
            columns=sql.SQL(", ").join(column_identifiers),
            values=sql.SQL(", ").join(value_identifiers),
        )
        return insert_query, tuple(params)

    def _embedding_model_name(self) -> str | None:
        if self._settings.use_openai:
            return self._settings.openai_embedding_model
        return self._settings.llm_model

    def _serialize_embedding(self, embedding: list[float]) -> Any:
        if self._settings.embedding_storage_format == "json":
            return Json(embedding)
        return "[" + ",".join(f"{value:.12g}" for value in embedding) + "]"
