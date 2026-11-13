"""Read and normalize source data. TODO: implement functions."""
"""Đọc và chuẩn hóa dữ liệu nguồn PDF OpenStax, chương 5 và chương 6."""
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from .models import DocumentPage

log = logging.getLogger(__name__)

EMPTY_THRESHOLD = 200  # dưới ngưỡng coi là trang gần như rỗng


def normalize_text(text: str) -> str:
    """Chuẩn hóa Unicode và khoảng trắng nhưng giữ lại xuống dòng (cấu trúc)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_pdf(path: Path, document_id: str, source: str,
             page_numbers: Iterable[int] | None = None) -> list[DocumentPage]:
    """Trích text từng trang vật lý (đánh số từ 1) và ghi nhận trang rỗng/lỗi, page_numbers=None nghĩa là đọc toàn bộ PDF. OCR không nằm trong hàm này."""
    reader = PdfReader(path)
    total = len(reader.pages)
    numbers = list(page_numbers) if page_numbers is not None else list(range(1, total + 1))
    pages: list[DocumentPage] = []
    for number in numbers:
        if not 1 <= number <= total:
            raise ValueError(f"Trang {number} nằm ngoài 1..{total}")
        error = None
        try:
            text = normalize_text(reader.pages[number - 1].extract_text() or "")
        except Exception as exc:  # pypdf có thể lỗi theo nhiều kiểu; ghi lại thay vì bỏ qua
            text, error = "", f"{type(exc).__name__}: {exc}"
            log.warning("Lỗi trích text trang %d: %s", number, error)
        metadata: dict[str, Any] = {"chars": len(text), "empty": len(text) < EMPTY_THRESHOLD}
        if error:
            metadata["error"] = error
        pages.append(DocumentPage(document_id=document_id, source=source,
                                  page=number, text=text, metadata=metadata))
    return pages


def section_for(chapter: dict[str, Any], printed_page: int) -> dict[str, Any]:
    """Mục của trang in này, tính theo trang bắt đầu của mục trong mục lục.
    Giới hạn: một trang có thể chứa cuối mục này và đầu mục kia; trang đó
    được gán cho mục bắt đầu gần nhất tính tới trang đó.
    """
    current = chapter["sections"][0]
    for section in chapter["sections"]:
        if section["printed_start"] <= printed_page:
            current = section
    return current


def load_corpus(config_path: Path) -> tuple[dict[str, Any], list[DocumentPage]]:
    """Đọc cấu hình, trích các trang nội dung hợp lệ và gắn metadata truy vết/lọc."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    root = config_path.resolve().parent.parent
    pdf_path = root / config["local_path"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"Không thấy PDF: {pdf_path}")

    by_page: dict[int, dict[str, Any]] = {}
    for chapter in config["chapters"]:
        for number in range(chapter["pdf_start"], chapter["pdf_end"] + 1):
            by_page[number] = chapter

    pages = load_pdf(pdf_path, config["source_id"], pdf_path.name, sorted(by_page))
    for page in pages:
        chapter = by_page[page.page]
        printed = page.page - config["page_offset"]
        section = section_for(chapter, printed)
        page.metadata.update({
            "page_id": f"{config['source_id']}:p{page.page}",
            "printed_page": printed,
            "chapter": chapter["chapter"],
            "chapter_title": chapter["title"],
            "section": section["section"],
            "section_title": section["title"],
        })
    return config, pages
