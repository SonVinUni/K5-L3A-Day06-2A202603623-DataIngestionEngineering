# Benchmark

Bộ câu hỏi ≥20 (tối thiểu 15 dev / 5 test), tối đa 3 câu có filter (≥1 câu test),
dùng chung cho cả ba chiến lược A/B/C.

## Định dạng questions.json

Mảng JSON, mỗi câu:

```json
{
  "id": "q01",
  "split": "dev",
  "type": "truc_tiep | dien_thu_lai | dieu_kien_ngoai_le | metadata_filter",
  "question": "Câu hỏi viết tay, KHÔNG chứa đáp án/gold source",
  "expected_answer": "Đáp án mong đợi",
  "gold_source_id": "openstax-ics-web",
  "gold_pages": [214],
  "evidence_quote": "Trích nguyên văn (sau chuẩn hóa) từ corpus, đã kiểm chứng bằng browse_corpus.py",
  "filter": {"chapter": 5}
}
```

- `gold_pages`: số trang PDF (xem header `=== PDF PAGE n | in m | chuong x | muc y z ===` trong
  `starter/results/corpus_text.txt`; `in m` là trang in).
- `filter`: chỉ nhận khóa `chapter` (5|6) và `section` (vd "5.2"); bỏ khóa này nếu câu không dùng filter.
- Kiểm chứng evidence: `python3 starter/scripts/browse_corpus.py find "đoạn trích"` — kết quả phải nằm
  trong `gold_pages`.
- Chạy kiểm tra: `python3 starter/scripts/validate_benchmark.py` (OK khi không có LỖI).
- Tách dev/test và chốt tiêu chí chọn cấu hình TRƯỚC khi chạy thử (RULES).
