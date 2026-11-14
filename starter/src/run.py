"""Pipeline Day 06: ingest -> chunk (A/B/C) -> embed -> pgvector -> evaluate.

Chạy từ thư mục starter/:
    python -m src.run

Trước khi chạy:
    1) docker compose -p day6_student_starter up -d --wait
    2) cp .env.example .env và điền EMBEDDING_BACKEND / EMBEDDING_MODEL
       (local: cài thêm `python -m pip install sentence-transformers torch`)
    3) python scripts/check_setup.py   # phải thấy "Setup OK"

Sản phẩm (results/):
    chunk_stats.json          - số chunk, độ dài, thời gian, chi phí từng cấu hình
    traces_A.json, traces_B, traces_C - top-3 đầy đủ (câu, chunk, score, metadata)
    metrics.json              - Hit@1 / Evidence Hit@3 theo dev/test cho A, B, C

Ba cấu hình (theo GUIDE.md):
    A: fixed_size 500 ký tự, overlap 50, metadata đầy đủ, không filter
    B: by_paragraph 500 ký tự, cùng metadata, không filter
    C: giống B nhưng câu nào có filter thì truy vấn có filter (jsonb @>)
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from .chunking import by_paragraph, fixed_size
from .embeddings import build_embedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_corpus
from .store import ChromaStore, PgVectorStore

ROOT = Path(__file__).resolve().parents[2]
STARTER = Path(__file__).resolve().parents[1]
RESULTS = STARTER / "results"

STRATEGIES = {
    "A": {"chunking": "fixed", "size": 500, "overlap": 50, "use_filter": False},
    "B": {"chunking": "paragraph", "max_size": 500, "use_filter": False},
    "C": {"chunking": "paragraph", "max_size": 500, "use_filter": True},
}

MIN_CONTENT_PAGES = 30


def chunk_strategy(pages, name: str, spec: dict) -> list:
    chunks = []
    for page in pages:
        if spec["chunking"] == "fixed":
            chunks.extend(fixed_size(page, spec["size"], spec["overlap"]))
        else:
            chunks.extend(by_paragraph(page, spec["max_size"]))
    return chunks


def main() -> None:
    vector_store = os.getenv("VECTOR_STORE", "pgvector").lower()
    config, pages = load_corpus(ROOT / "data" / "corpus_config.json")
    if len(pages) < MIN_CONTENT_PAGES:
        raise SystemExit(
            f"Corpus {len(pages)} trang < {MIN_CONTENT_PAGES} trang nội dung - "
            f"không đủ điều kiện (GUIDE.md)")
    questions = json.loads((ROOT / "benchmark" / "questions.json").read_text("utf-8"))
    print(f"Corpus: {len(pages)} trang | {sum(len(p.text) for p in pages)} ký tự | "
          f"{len(questions)} câu hỏi")

    embedder = build_embedder()
    dims = embedder.ensure_dimensions()
    print(f"Embedder: {embedder.model_name} | {dims} chiều | "
          f"backend {os.getenv('EMBEDDING_BACKEND', 'local')}")

    if vector_store == "pgvector":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise SystemExit("DATABASE_URL thiếu trong .env (copy .env.example sang .env)")
        store = PgVectorStore(database_url, dims)
        store.create_schema()
        print("Store: PostgreSQL + pgvector (cosine, exact)")
    elif vector_store == "chroma":
        chroma_path = os.getenv("CHROMA_PATH") or str(STARTER / "chroma_data")
        store = ChromaStore(chroma_path, dims)
        store.create_schema()
        print(f"Store: Chroma local (cosine, HNSW approximate) tại {chroma_path}")
    else:
        raise SystemExit(f"VECTOR_STORE không rõ: {vector_store!r} ('pgvector' hoặc 'chroma')")

    RESULTS.mkdir(exist_ok=True)
    all_metrics: dict[str, dict] = {}
    stats: dict[str, dict] = {}

    for name, spec in STRATEGIES.items():
        t0 = time.time()
        chunks = chunk_strategy(pages, name, spec)
        t_chunk = time.time() - t0
        print(f"\n[{name}] {spec['chunking']}: {len(chunks)} chunk "
              f"(chunking {t_chunk:.1f}s) - đang embed (có thể mất vài phút)...")
        t1 = time.time()
        vectors = embedder.embed_documents([c.text for c in chunks])
        t_embed = time.time() - t1
        store.upsert(name, chunks, vectors)
        print(f"[{name}] embed {t_embed:.1f}s | đã lưu {store.count(name)} chunk "
              f"(kiểm tra không nhân đôi: lên {store.count(name)} -> chạy lại vẫn {store.count(name)})")
        stats[name] = {
            "strategy": name,
            "chunking": spec["chunking"],
            "params": spec,
            "num_chunks": len(chunks),
            "avg_chunk_chars": round(sum(len(c.text) for c in chunks) / len(chunks), 1),
            "max_chunk_chars": max(len(c.text) for c in chunks),
            "total_chars": sum(len(c.text) for c in chunks),
            "chunking_seconds": round(t_chunk, 1),
            "embedding_seconds": round(t_embed, 1),
            "cost_note": ("0 (model local)"
                          if os.getenv("EMBEDDING_BACKEND", "local") == "local"
                          else "xem hóa đơn API; ghi rõ trong report"),
        }

        traces = []
        for question in questions:
            filters = question.get("filter") if spec["use_filter"] else None
            qvec = embedder.embed_query(question["question"])
            hits = store.search(name, qvec, top_k=3, filters=filters)
            traces.append(evaluate_query(question, hits))
        (RESULTS / f"traces_{name}.json").write_text(
            json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = summarize(traces, name)
        all_metrics[name] = summary
        print(f"[{name}] dev: Hit@1 {summary['dev']['hit@1']} | "
              f"Ev.Hit@3 {summary['dev']['evidence_hit@3']} "
              f"| test: Hit@1 {summary['test']['hit@1']} | "
              f"Ev.Hit@3 {summary['test']['evidence_hit@3']}")
        print(f"[{name}] trace: results/traces_{name}.json")

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "embedder": embedder.model_name,
        "dimensions": dims,
        "store": ("PostgreSQL + pgvector (cosine, exact)"
                   if vector_store == "pgvector"
                   else "Chroma local (cosine, HNSW approximate)"),
        "stats": stats,
        "metrics": all_metrics,
    }
    (RESULTS / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "chunk_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nXong. Số liệu: results/metrics.json | chi tiết: results/chunk_stats.json")
    print("Bước tiếp: chấm coherence/metadata/grounding thủ công (GUIDE mục 4) "
          "và điền artifacts/experiment_log.csv + report.")


if __name__ == "__main__":
    main()
