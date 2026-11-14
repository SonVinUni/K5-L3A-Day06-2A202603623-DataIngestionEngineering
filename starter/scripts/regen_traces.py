"""Viết lại traces_A/B/C.json kèm metadata top-3, không embed lại.

Store (chroma_data/) đã có sẵn vector; chỉ embed lại 21 câu hỏi rồi
search + ghi trace. Dùng khi trace cũ thiếu trường metadata.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from src.embeddings import build_embedder
from src.evaluation import evaluate_query
from src.store import ChromaStore

ROOT = Path(__file__).resolve().parents[2]
STARTER = Path(__file__).resolve().parents[1]
QUESTIONS = json.loads((ROOT / "benchmark" / "questions.json").read_text("utf-8"))

USE_FILTER = {"A": False, "B": False, "C": True}

store = ChromaStore(str(STARTER / "chroma_data"), 768)
embedder = build_embedder()
for name in "ABC":
    traces = []
    for q in QUESTIONS:
        filters = q.get("filter") if USE_FILTER[name] else None
        hits = store.search(name, embedder.embed_query(q["question"]), top_k=3, filters=filters)
        traces.append(evaluate_query(q, hits))
    out = STARTER / "results" / f"traces_{name}.json"
    out.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    h1d = sum(t["hit@1"] for t in traces if t["split"] == "dev")
    h3d = sum(t["evidence_hit@3"] for t in traces if t["split"] == "dev")
    h1t = sum(t["hit@1"] for t in traces if t["split"] == "test")
    h3t = sum(t["evidence_hit@3"] for t in traces if t["split"] == "test")
    print(f"[{name}] dev Hit@1 {h1d}/16 Ev.Hit@3 {h3d}/16 | test Hit@1 {h1t}/5 Ev.Hit@3 {h3t}/5 | {out.name}")
print(f"Model: {embedder.model_name} | backend {os.getenv('EMBEDDING_BACKEND', 'local')}")
