"""Kiểm tra benchmark/questions.json với corpus."""
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data" / "corpus_config.json"
QUESTIONS = ROOT / "benchmark" / "questions.json"
REQUIRED = ["id", "split", "type", "question", "expected_answer",
            "gold_source_id", "gold_pages", "evidence_quote"]
FILTER_KEYS = {"chapter", "section"}


def norm(text: str) -> str:
    """So khớp không phụ thuộc xuống dòng, khoảng trắng hay kiểu nháy."""
    text = unicodedata.normalize("NFKC", text)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(a, b)
    return " ".join(text.split())


def main() -> int:
    config, pages = load_corpus(CONFIG)
    by_page = {p.page: p for p in pages}
    normalized = {n: norm(p.text) for n, p in by_page.items()}
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    ids = [q.get("id") for q in questions]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"id trùng: {dup}")

    for q in questions:
        qid = q.get("id", "?")
        missing = [k for k in REQUIRED if k not in q or q[k] in (None, "", [])]
        if missing:
            errors.append(f"{qid}: thiếu trường {missing}")
            continue
        if q["split"] not in ("dev", "test"):
            errors.append(f"{qid}: split phải là 'dev' hoặc 'test'")
        if q["gold_source_id"] != config["source_id"]:
            errors.append(f"{qid}: gold_source_id khác {config['source_id']!r}")
        bad_pages = [p for p in q["gold_pages"] if p not in by_page]
        if bad_pages:
            errors.append(f"{qid}: gold_pages ngoài corpus: {bad_pages}")
            continue
        quote = norm(q["evidence_quote"])
        holders = [n for n, text in normalized.items() if quote in text]
        in_gold = [n for n in q["gold_pages"] if n in holders]
        if not in_gold:
            errors.append(f"{qid}: evidence_quote KHÔNG nằm ở gold_pages {q['gold_pages']}"
                          + (f" (nhưng có ở trang {holders})" if holders else ""))
        extra = [n for n in holders if n not in q["gold_pages"]]
        if extra:
            shown = extra[:5] + (["..."] if len(extra) > 5 else [])
            warnings.append(f"{qid}: evidence cũng xuất hiện ở {len(extra)} trang khác {shown}; "
                            "nếu hợp lệ thì thêm vào gold_pages")
        if len(quote) < 30:
            warnings.append(f"{qid}: evidence_quote rất ngắn ({len(quote)} ký tự), dễ khớp nhầm")
        flt = q.get("filter")
        if flt:
            if not isinstance(flt, dict) or not set(flt) <= FILTER_KEYS:
                errors.append(f"{qid}: filter chỉ nhận khóa {sorted(FILTER_KEYS)}")
            elif not any(all(by_page[n].metadata[k] == v for k, v in flt.items())
                         for n in q["gold_pages"]):
                errors.append(f"{qid}: không gold_page nào thỏa filter {flt}")

    total = len(questions)
    dev = sum(q.get("split") == "dev" for q in questions)
    test = sum(q.get("split") == "test" for q in questions)
    filt = [q for q in questions if q.get("filter")]
    filt_test = sum(q.get("split") == "test" for q in filt)
    if total < 20:
        errors.append(f"Cần ≥20 câu, hiện có {total}")
    if dev < 15:
        errors.append(f"Cần ≥15 câu dev, hiện có {dev}")
    if test < 5:
        errors.append(f"Cần ≥5 câu test, hiện có {test}")
    if len(filt) < 3:
        errors.append(f"Cần ≥3 câu có filter, hiện có {len(filt)}")
    if filt_test < 1:
        errors.append("Cần ≥1 câu test có filter")

    print(f"Tổng {total} | dev {dev} | test {test} | có filter {len(filt)} (test: {filt_test})")
    types: dict[str, int] = {}
    for q in questions:
        types[q.get("type", "?")] = types.get(q.get("type", "?"), 0) + 1
    print("Theo loại:", types)
    for w in warnings:
        print("CẢNH BÁO:", w)
    for e in errors:
        print("LỖI:", e)
    print("OK" if not errors else f"{len(errors)} lỗi cần sửa")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())