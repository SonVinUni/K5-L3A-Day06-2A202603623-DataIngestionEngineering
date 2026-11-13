"""Tạo data/manifest.json từ data/corpus_config.json và PDF."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pypdf import PdfReader

from src.ingestion import load_corpus, load_pdf

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "data" / "corpus_config.json"
OUT = ROOT / "data" / "manifest.json"

config, pages = load_corpus(CONFIG)
pdf_path = ROOT / config["local_path"]

# Kiểm tra độ lệch trang
problems = []
for chapter in config["chapters"]:
    after = chapter["pdf_end"] + 1
    text = load_pdf(pdf_path, config["source_id"], pdf_path.name, [after])[0].text
    if not text.startswith("Chapter Review"):
        problems.append(f"Chương {chapter['chapter']}: trang PDF {after} không bắt đầu bằng "
                        f"'Chapter Review' (thấy: {text[:40]!r})")

chapters = []
for chapter in config["chapters"]:
    count = chapter["pdf_end"] - chapter["pdf_start"] + 1
    chapters.append({
        "chapter": chapter["chapter"], "title": chapter["title"],
        "pdf_pages": [chapter["pdf_start"], chapter["pdf_end"]],
        "printed_pages": [chapter["pdf_start"] - config["page_offset"],
                          chapter["pdf_end"] - config["page_offset"]],
        "content_pages": count,
    })

manifest = {
    **{k: config[k] for k in ("source_id", "title", "publisher", "source_url", "local_path",
                              "license", "license_note", "permission_note", "accessed_at",
                              "page_offset", "page_rule")},
    "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
    "chapters": chapters,
    "totals": {
        "physical_pages_in_pdf": len(PdfReader(pdf_path).pages),
        "content_pages": len(pages),
        "chars": sum(p.metadata["chars"] for p in pages),
        "near_empty_pages": [p.page for p in pages if p.metadata["empty"]],
        "extraction_errors": [p.page for p in pages if "error" in p.metadata],
    },
    "pages": [
        {"page_id": p.metadata["page_id"], "pdf_page": p.page,
         "printed_page": p.metadata["printed_page"], "chapter": p.metadata["chapter"],
         "section": p.metadata["section"], "chars": p.metadata["chars"],
         "empty": p.metadata["empty"]}
        for p in pages
    ],
}
OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Đã ghi {OUT}")
print(f"Trang nội dung: {manifest['totals']['content_pages']} | ký tự: {manifest['totals']['chars']}")
print("Trang gần rỗng:", manifest["totals"]["near_empty_pages"] or "không có")
print("Lỗi trích text:", manifest["totals"]["extraction_errors"] or "không có")
for problem in problems:
    print("CẢNH BÁO:", problem)
if not problems:
    print("Kiểm tra độ lệch trang: OK")