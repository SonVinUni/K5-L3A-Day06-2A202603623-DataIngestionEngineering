"""Lưu và truy vấn vector bằng PostgreSQL + pgvector.

Bảng day6_chunks: mỗi chiến lược (A/B/C) là một "sách vở" riêng, phân biệt
bởi cột strategy. Vector được chuẩn hóa (normalize_embeddings=True) nên
khoảng cách cosine <=> tương đương 1 - cosine similarity.

- upsert: ON CONFLICT (strategy, chunk_id) DO NOTHING -> chạy lại không
  nhân đôi; sau đó xóa các chunk của strategy không còn thuộc corpus
  (xử lý tài liệu đổi). Ghi nhận: giữ bản vector cũ nếu chunk_id trùng
  (đủ cho thí nghiệm; không ghi đè).
- search: cosine distance, lọc metadata bằng jsonb @>; mọi giá trị do
  người dùng cấp được tham số hóa (chống SQL injection); khóa lọc giới
  hạn trong danh sách đóng (RULES: không cho khóa lạ).
"""
import json
from typing import Any

import psycopg

from .models import Chunk

# Chỉ cho phép lọc theo các khóa metadata này (không để lộ cột khác)
FILTER_KEYS = {"chapter", "section", "printed_page", "chapter_title", "section_title"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS day6_chunks (
    strategy    text NOT NULL,
    chunk_id    text NOT NULL,
    document_id text NOT NULL,
    source      text NOT NULL,
    page        integer NOT NULL,
    text        text NOT NULL,
    metadata    jsonb NOT NULL DEFAULT '{}',
    embedding   vector({dim}) NOT NULL,
    PRIMARY KEY (strategy, chunk_id)
);
"""


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError(f"Số chiều phải > 0, nhận {dimensions}")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self) -> "psycopg.Connection":
        return psycopg.connect(self.database_url, autocommit=False)

    def create_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                row = cur.execute(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()
                if row is None:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(_SCHEMA.format(dim=self.dimensions))
            conn.commit()

    def upsert(self, strategy: str, chunks: list[Chunk],
               vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Số chunk ({len(chunks)}) khác số vector ({len(vectors)})")
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"chunk {chunk.chunk_id}: vector {len(vector)} chiều, "
                    f"đóng ý {self.dimensions}")
        new_ids = [c.chunk_id for c in chunks]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO day6_chunks
                        (strategy, chunk_id, document_id, source, page,
                         text, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id) DO NOTHING
                    """,
                    [
                        (strategy, c.chunk_id, c.document_id, c.source,
                         c.page, c.text, json.dumps(c.metadata),
                         json.dumps(list(v)))
                        for c, v in zip(chunks, vectors)
                    ],
                )
                # Xóa chunk của strategy không còn thuộc corpus lần này
                stale = [row[0] for row in cur.execute(
                    "SELECT chunk_id FROM day6_chunks WHERE strategy = %s",
                    (strategy,),
                ).fetchall() if row[0] not in set(new_ids)]
                for old in stale:
                    cur.execute(
                        "DELETE FROM day6_chunks "
                        "WHERE strategy = %s AND chunk_id = %s",
                        (strategy, old),
                    )
            conn.commit()
        return len(chunks)

    def count(self, strategy: str) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            row = cur.execute(
                "SELECT COUNT(*) FROM day6_chunks WHERE strategy = %s",
                (strategy,),
            ).fetchone()
            return int(row[0])

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where = ["strategy = %s"]
        params: list[Any] = [json.dumps(list(query_vector)), strategy]
        for key, value in (filters or {}).items():
            if key not in FILTER_KEYS:
                raise ValueError(
                    f"Khóa lọc không cho phép: {key!r} (đóng ý {sorted(FILTER_KEYS)})")
            where.append("metadata @> %s::jsonb")
            params.append(json.dumps({key: value}))
        params.append(top_k)
        sql = f"""
            SELECT chunk_id, page, text,
                   1 - (embedding <=> %s::vector) AS similarity,
                   metadata
            FROM day6_chunks
            WHERE {' AND '.join(where)}
            ORDER BY similarity DESC
            LIMIT %s
        """
        with self._connect() as conn, conn.cursor() as cur:
            rows = cur.execute(sql, params).fetchall()
        return [
            {"chunk_id": r[0], "page": r[1], "text": r[2],
             "similarity": round(float(r[3]), 6), "metadata": r[4]}
            for r in rows
        ]


# ---------------------------------------------------------------- Chroma local
class ChromaStore:
    """Store dự phòng theo CHECKPOINTS.md: Chroma local, không cần Docker.

    Một collection cho mỗi chiến lược (day6_A/B/C), không gian cosine
    (HNSW - tìm kiếm xấp xỉ, ghi nhận trong report). Chroma metadata chỉ
    nhận str/int/float -> loại bỏ giá trị bool/dict; filter dùng câu
    where = {khóa: giá trị} (nghĩa AND), tương đương jsonb @> của pgvector.
    Lưu ý: collection giữ theo số chiều lúc tạo; đổi model embedding khác
    chiều -> xóa thư mục Chroma và chạy lại.
    """

    def __init__(self, chroma_path: str, dimensions: int) -> None:
        import chromadb
        if dimensions <= 0:
            raise ValueError(f"Số chiều phải > 0, nhận {dimensions}")
        self._client = chromadb.PersistentClient(path=chroma_path)
        self.dimensions = dimensions

    def _collection(self, strategy: str):
        return self._client.get_or_create_collection(
            f"day6_{strategy}",
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"dimension": self.dimensions},
        )

    def create_schema(self) -> None:
        """Chroma tự tạo collection; không có bước nào khác."""
        return None

    @staticmethod
    def _flat_metadata(chunk: "Chunk") -> dict:
        out: dict = {}
        for key, value in chunk.metadata.items():
            if isinstance(value, bool):
                continue  # Chroma metadata không nhận bool
            if isinstance(value, (str, int, float)):
                out[key] = value
        out["document_id"] = chunk.document_id
        out["source"] = chunk.source
        out["page"] = chunk.page
        return out

    def upsert(self, strategy: str, chunks: list[Chunk],
               vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Số chunk ({len(chunks)}) khác số vector ({len(vectors)})")
        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"chunk {chunk.chunk_id}: vector {len(vector)} chiều, "
                    f"đóng ý {self.dimensions}")
        col = self._collection(strategy)
        col.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=[[float(x) for x in v] for v in vectors],
            documents=[c.text for c in chunks],
            metadatas=[self._flat_metadata(c) for c in chunks],
        )
        # Xóa chunk không còn thuộc corpus lần này (không nhân đôi)
        new_ids = {c.chunk_id for c in chunks}
        stale = set(col.get(include=[])["ids"]) - new_ids
        if stale:
            col.delete(ids=sorted(stale))
        return len(chunks)

    def count(self, strategy: str) -> int:
        return self._collection(strategy).count()

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        where: dict[str, Any] | None = None
        if filters:
            where = {}
            for key, value in filters.items():
                if key not in FILTER_KEYS:
                    raise ValueError(
                        f"Khóa lọc không cho phép: {key!r} "
                        f"(đóng ý {sorted(FILTER_KEYS)})")
                where[key] = value
        res = self._collection(strategy).query(
            query_embeddings=[[float(x) for x in query_vector]],
            where=where,
            n_results=top_k,
        )
        out = []
        for i, cid in enumerate(res["ids"][0]):
            meta = res["metadatas"][0][i] or {}
            out.append({
                "chunk_id": cid,
                "page": meta.get("page"),
                "text": res["documents"][0][i],
                "similarity": round(1 - float(res["distances"][0][i]), 6),
                "metadata": meta,
            })
        return out
