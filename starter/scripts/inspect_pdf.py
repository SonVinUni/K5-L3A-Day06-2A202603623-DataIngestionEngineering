import csv
import sys
from pathlib import Path

from pypdf import PdfReader

pdf_path = Path(sys.argv[1])
reader = PdfReader(pdf_path)
rows = []
for index, page in enumerate(reader.pages, start=1):
    text = (page.extract_text() or "").strip()
    first_line = text.splitlines()[0][:70] if text else ""
    rows.append((index, len(text), first_line))

out = Path("results/page_inventory.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["pdf_page", "chars", "first_line"])
    writer.writerows(rows)

print(f"{len(rows)} trang, đã lưu {out}")
print("Trang gần như rỗng (<200 ký tự):", [r[0] for r in rows if r[1] < 200])