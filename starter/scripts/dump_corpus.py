"""Xuất text đã chuẩn hóa của toàn bộ trang nội dung ra results/corpus_text.txt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
_, pages = load_corpus(ROOT / "data" / "corpus_config.json")
out = Path(__file__).resolve().parents[1] / "results" / "corpus_text.txt"
out.parent.mkdir(exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    for p in pages:
        m = p.metadata
        f.write(f"\n=== PDF PAGE {p.page} | in {m['printed_page']} | chuong {m['chapter']} "
                f"| muc {m['section']} {m['section_title']} ===\n{p.text}\n")
print(f"Đã ghi {out} ({out.stat().st_size // 1024} KB, {len(pages)} trang)")