"""Hai cách chia chunk cho bài Day 06.

- fixed_size: cửa sổ ký tự trượt có overlap (cấu hình A).
- by_paragraph: gom đoạn văn, cắt cứng chỉ khi đoạn quá dài (cấu hình B, C).

Mọi chunk giữ metadata của trang nguồn (page_id, printed_page, chapter, section...)
để truy vết và lọc.
"""
from .models import Chunk, DocumentPage


def _make_chunk(page: DocumentPage, index: int, text: str) -> Chunk:
    meta = dict(page.metadata)
    meta["chunk_index"] = index
    meta["chunk_chars"] = len(text)
    return Chunk(
        chunk_id=f"{page.document_id}:p{page.page}:{index}",
        document_id=page.document_id,
        source=page.source,
        page=page.page,
        text=text,
        metadata=meta,
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    """Cửa sổ size ký tự, bước đi size - overlap; dừng khi đã phủ hết trang.

    Trang rỗng trả về []. overlap >= size thì không tiến được -> ValueError.
    """
    if size <= 0:
        raise ValueError(f"size phải > 0, nhận {size}")
    if overlap >= size:
        raise ValueError(f"overlap phải < size (overlap={overlap}, size={size})")
    text = page.text
    chunks: list[Chunk] = []
    if not text:
        return chunks
    n = len(text)
    step = size - overlap
    start, index = 0, 0
    while start < n:
        window = text[start:start + size]
        chunks.append(_make_chunk(page, index, window))
        if start + size >= n:
            break
        start += step
        index += 1
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    """Gom các đoạn văn (phân tách bằng \\n\\n) tới tổng dài nhất max_size ký tự.

    Giới hạn (ghi trong report):
    - Đoạn riêng lẻ > max_size buộc cắt cứng thành các cửa sổ max_size (không
      overlap) - đây là fallback, chunk bị cắt giữa đoạn dễ bị trừ điểm coherence.
    - Trang không có \\n\\n nào (text liền khít) thì về bản chất giống fixed-size.
    """
    if max_size <= 0:
        raise ValueError(f"max_size phải > 0, nhận {max_size}")
    paragraphs = [p for p in (s.strip() for s in page.text.split("\n\n")) if p]
    chunks: list[Chunk] = []

    def emit(block: str) -> None:
        chunks.append(_make_chunk(page, len(chunks), block))

    def split_oversized(paragraph: str) -> None:
        for start in range(0, len(paragraph), max_size):
            emit(paragraph[start:start + max_size])

    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_size:
            if current:
                emit("\n\n".join(current))
                current, current_len = [], 0
            split_oversized(paragraph)
            continue
        if current and current_len + len(paragraph) + 2 > max_size:
            emit("\n\n".join(current))
            current, current_len = [paragraph], len(paragraph)
        else:
            current.append(paragraph)
            current_len += len(paragraph) + (2 if len(current) > 1 else 0)
    if current:
        emit("\n\n".join(current))
    return chunks
