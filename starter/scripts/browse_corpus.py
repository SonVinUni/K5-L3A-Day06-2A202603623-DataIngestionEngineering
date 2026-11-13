"""Xem text đã chuẩn hóa của một trang, hoặc tìm trang chứa một cụm từ."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_corpus  # noqa: E402

CONFIG = Path(__file__).resolve().parents[2] / "data" / "corpus_config.json"


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("page", "find"):
        print(__doc__)
        return 1
    _, pages = load_corpus(CONFIG)
    if argv[1] == "page":
        number = int(argv[2])
        page = next((p for p in pages if p.page == number), None)
        if page is None:
            print(f"Trang PDF {number} không nằm trong corpus "
                  f"({pages[0].page}-{pages[-1].page}, trừ khoảng giữa hai chương).")
            return 1
        m = page.metadata
        print(f"[pdf {number} | in {m['printed_page']} | chương {m['chapter']} | mục {m['section']}]")
        print(page.text)
        return 0
    needle = " ".join(argv[2:]).lower()
    found = 0
    for page in pages:
        count = " ".join(page.text.lower().split()).count(needle)
        if count:
            m = page.metadata
            print(f"pdf {page.page} (in {m['printed_page']}, chương {m['chapter']}, "
                  f"mục {m['section']} {m['section_title']}): {count} lần")
            found += 1
    print(f"{found} trang chứa {needle!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))