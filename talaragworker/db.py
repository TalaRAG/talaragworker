from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

        insert_query = sql.SQL(
            """
            INSERT INTO {embeddings_table} (
                {document_id_column},
                {chunk_index_column},
                {content_column},
                {vector_column}
            )
            VALUES (%s, %s, %s, {vector_value})
            """
        ).format(
            embeddings_table=sql.Identifier(self._settings.document_embeddings_table),
            document_id_column=sql.Identifier(self._settings.document_embeddings_document_id_column),
            chunk_index_column=sql.Identifier(self._settings.document_embeddings_chunk_index_column),
            content_column=sql.Identifier(self._settings.document_embeddings_content_column),
            vector_column=sql.Identifier(self._settings.document_embeddings_vector_column),
            vector_value=vector_value,
        )

        try:
            with self._connection.cursor() as cursor:
                cursor.execute(delete_query, (document_id,))
                for chunk in chunks:
                    cursor.execute(
                        insert_query,
                        (
                            document_id,
                            chunk.chunk_index,
                            chunk.content,
                            self._serialize_embedding(chunk.embedding),
                        ),
                    )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def _serialize_embedding(self, embedding: list[float]) -> Any:
        if self._settings.embedding_storage_format == "json":
            return Json(embedding)
        return "[" + ",".join(f"{value:.12g}" for value in embedding) + "]"
