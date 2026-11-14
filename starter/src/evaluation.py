"""Chấm truy xuất tự động (Hit@1, Evidence Hit@3) và lưu trace.

Định nghĩa theo BENCHMARK.md:
- Một hit khi chunk thuộc gold source VÀ gold page (hoặc trang thay thế
  được ghi trong câu hỏi) VÀ chứa ĐỦ evidence_quote đã chuẩn hóa.
- Hit@1 = số câu top-1 hit / số câu.
- Evidence Hit@3 = số câu có ít nhất 1 hit trong top-3 / số câu.

Lưu ý (ghi trong report): matching dựa chuẩn NFKC + gộp khoảng trắng +
thống nhất nháy giống validate_benchmark.py. Không suy ra nhãn coherence/
grounding thủ công từ đây - đó là chấm tay riêng.
"""
import unicodedata
from typing import Any


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(a, b)
    return " ".join(text.split())


def chunk_hits(chunk: dict[str, Any], question: dict[str, Any]) -> bool:
    """True khi chunk đúng gold source + gold page + chứa đủ evidence."""
    meta = chunk.get("metadata") or {}
    ok_source = meta.get("document_id") == question.get("gold_source_id")
    ok_page = chunk.get("page") in question.get("gold_pages", [])
    evidence = _norm(question.get("evidence_quote", ""))
    ok_evidence = bool(evidence) and evidence in _norm(chunk.get("text", ""))
    return ok_source and ok_page and ok_evidence


def evaluate_query(question: dict[str, Any],
                   hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Trả về trace: hit@1, hit@3, danh sách top-3 (id, text, score, metadata).

    hits: kết quả search() của store, đã theo đúng thứ tự giống (gần nhất trước).
    """
    top1_hit = bool(hits) and chunk_hits(hits[0], question)
    top3_hit = any(chunk_hits(h, question) for h in hits[:3])
    trace = {
        "question_id": question.get("id"),
        "split": question.get("split"),
        "question": question.get("question"),
        "gold_pages": question.get("gold_pages"),
        "hit@1": top1_hit,
        "evidence_hit@3": top3_hit,
        "top3": [
            {"chunk_id": h.get("chunk_id"),
             "page": (h.get("metadata") or {}).get("printed_page") or h.get("page"),
             "similarity": h.get("similarity"),
             "hit": chunk_hits(h, question),
             "text_preview": (h.get("text") or "")[:300]}
            for h in hits[:3]
        ],
        "filter": question.get("filter"),
    }
    return trace


def summarize(traces: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    """Tóm tắt Hit@1 và Evidence Hit@3 theo dev/test cho một chiến lược."""
    out: dict[str, Any] = {"strategy": strategy}
    for split in ("dev", "test"):
        subset = [t for t in traces if t.get("split") == split]
        n = len(subset)
        h1 = sum(1 for t in subset if t.get("hit@1"))
        h3 = sum(1 for t in subset if t.get("evidence_hit@3"))
        out[split] = {
            "n": n,
            "hit@1": f"{h1}/{n}",
            "evidence_hit@3": f"{h3}/{n}",
            "hit@1_ratio": (h1 / n) if n else None,
            "evidence_hit@3_ratio": (h3 / n) if n else None,
            "missed": [t["question_id"] for t in subset
                       if not t.get("evidence_hit@3")],
        }
    return out
