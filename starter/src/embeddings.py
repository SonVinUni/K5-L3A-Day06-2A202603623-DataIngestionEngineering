"""Embedding: model local (Sentence Transformers) hoặc API OpenRouter.

Chặn bởi EMBEDDING_BACKEND trong .env:
- "local": cài `sentence-transformers` + `torch`, tải model EMBEDDING_MODEL
  (mặc định google/embeddinggemma-2, cần RAM ~4-8GB).
- "openrouter": dùng API key trong .env (OPENROUTER_API_KEY), model
  EMBEDDING_MODEL (vd "google/gemini-embedding-001" hoặc model free khác).

Không bao giờ fallback im lặng sang vector mock/ngẫu nhiên: lỗi model ->
nổ lỗi có thông báo rõ ràng (RULES).
"""
import os
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Query vector cùng không gian vector với document."""
        ...

    def ensure_dimensions(self) -> int:
        """Trả về số chiều vector (chạy 1 lần để biết nếu chưa gọi embed)."""
        ...


class LocalSentenceTransformerEmbedder:
    """Chạy trên CPU. Model mặc định google/embeddinggemma-2 (ngôn ngữ
    Anh; corpus OpenStax tiếng Anh). Có thể đổi sang all-MiniLM-L6-v2
    nếu máy yếu (kết quả khác -> phải làm lại toàn bộ thí nghiệm)."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu câu lệnh: python -m pip install sentence-transformers"
            ) from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        self.dimensions = self._model.get_sentence_embedding_dimension()
        self._model.max_seq_length = self._model.max_seq_length  # giữ mặc định

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=True,
        )
        return [list(map(float, row)) for row in vectors]

    def embed_query(self, question: str) -> list[float]:
        vec = self._model.encode([question], normalize_embeddings=True)[0]
        return list(map(float, vec))

    def ensure_dimensions(self) -> int:
        return self.dimensions


class OpenRouterEmbedder:
    """POST /embeddings (format OpenAI) qua api.openrouter.ai."""

    ENDPOINT = "https://api.openrouter.ai/v1/embeddings"

    def __init__(self, model_name: str) -> None:
        import json
        import urllib.request
        self.model_name = model_name
        self._api_key = os.getenv("OPENROUTER_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY trống trong .env - dùng backend local "
                "hoặc điền key."
            )
        self._req_cls = urllib.request
        self._json = json
        # Kiểm tra chiều từ response đầu; chưa gọi thì dimensions = None
        self.dimensions = None

    def _call(self, texts: list[str]) -> list[list[float]]:
        payload = self._json.dumps({
            "model": self.model_name,
            "input": texts,
        }).encode()
        request = self._req_cls.Request(
            self.ENDPOINT, data=payload, headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with self._req_cls.urlopen(request, timeout=120) as response:
            data = self._json.loads(response.read())
        vectors = [item["embedding"] for item in data["data"]]
        self.dimensions = len(vectors[0])
        return [list(map(float, v)) for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Chặn 25 bản/lần cho an toàn với giới hạn request của provider
        out: list[list[float]] = []
        for start in range(0, len(texts), 25):
            out.extend(self._call(texts[start:start + 25]))
        return out

    def embed_query(self, question: str) -> list[float]:
        return self._call([question])[0]

    def ensure_dimensions(self) -> int:
        if self.dimensions is None:
            self._call(["probe"])
        return self.dimensions


def build_embedder() -> Embedder:
    """Đọc .env (EMBEDDING_BACKEND, EMBEDDING_MODEL) và tạo embedder."""
    backend = os.getenv("EMBEDDING_BACKEND", "local").lower()
    model = os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-2")
    if backend == "local":
        return LocalSentenceTransformerEmbedder(model)
    if backend == "openrouter":
        return OpenRouterEmbedder(model)
    raise RuntimeError(f"EMBEDDING_BACKEND không rõ: {backend!r} (dùng 'local' hoặc 'openrouter')")
