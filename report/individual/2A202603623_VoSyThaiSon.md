# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  Chủ đề: computer systems + operating systems. Nguồn: sách mở OpenStax
  *Introduction to Computer Science* (Rice University, license CC BY 4.0 — tự tải,
  trích dẫn ghi nguồn). Corpus gồm chương 5 (PDF tr. 203–239) và chương 6
  (PDF tr. 249–294), tổng **83 trang nội dung, 246.985 ký tự** sau chuẩn hóa.
  Quy tắc tính trang (ghi trong `data/corpus_config.json`): đếm trang PDF có nội
  dung chương, loại bìa/mục lục/trang review giữa hai chương; trang in = trang
  PDF − 10 (`page_offset`). Manifest ở `data/manifest.json` (script
  `build_manifest.py` sinh ra, đã kiểm "độ lệch trang OK", 0 trang rỗng, 0 lỗi
  trích text).

- **Chuẩn hóa, lỗi và giới hạn:**
  Chuẩn hóa NFKC + gộp khoảng trắng, giữ xuống dòng để tách đoạn
  (`src/ingestion.py`). Không có trang rỗng hay lỗi trích. Giới hạn: pypdf trả
  text theo line-wrap của PDF, nên dấu `\n` không hẳn là ranh giới đoạn văn thật
  — cái này ảnh hưởng trực tiếp đến cấu hình B (mục coherence bên dưới).

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí:**
  Model: `google/embeddinggemma-2` (768 chiều), chạy **local** qua
  `sentence-transformers` trên CPU, không API key → chi phí 0. Vector store:
  **Chroma local** (cosine, HNSW — tìm kiếm xấp xỉ, không exact), dữ liệu nằm
  trong `starter/chroma_data/`. Lý do chọn Chroma thay vì pgvector: máy ở lớp
  không có Docker (`docker: command not found`), nên dùng phương án dự phòng
  ghi sẵn trong CHECKPOINTS.md. Lệnh chạy: `python -m src.run` từ `starter/`
  (chi tiết trong README). Thời gian embed: A ≈ 10p33s, B ≈ 10p23s, C ≈ 9p
  (CPU, bfloat16). Lỗi gặp khi setup (ghi theo RULES): (1) Docker không có →
  chuyển Chroma; (2) máy thiếu Pillow/torchvision để load processor của model
  multimodal → cài thêm; (3) tên model ban đầu ghi sai (embeddinggemma-2B) nên
  HF báo 401 Repository Not Found → sửa lại đúng repo.

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn:**
  Mỗi chunk mang `document_id`, `source`, `page` (PDF) + `printed_page`
  (trang in) + `chapter` (5/6) + `section` (vd 5.5, 6.3) + `chunk_index`.
  Hai trường lọc dùng trong benchmark: `chapter` (giá trị 5|6, lấy từ cấu hình
  chương trong corpus) và `section` (giá trị "5.5", "6.3"... lấy từ mục lục trong
  PDF, map theo trang bắt đầu của mục). Chọn vì corpus có đúng 2 chương với các
  mục đánh số rõ ràng → giá trị phân biệt được, không phải tự đoán.

## Cấu hình và benchmark

- **A / B / C:**
  - A: fixed 500 ký tự, overlap 50 (582 chunk, tổng 271.935 ký tự — có trùng do
    overlap), metadata đầy đủ, **không filter**.
  - B: paragraph max 500 (gom theo `\n\n`, đoạn > 500 cắt cứng), 534 chunk,
    tổng 246.985 ký tự (bằng corpus, không trùng), cùng metadata, không filter.
  - C: chunk + metadata y hệt B, khác duy nhất: **bật filter** (5 câu có filter
    thì truy vấn kèm điều kiện `chapter`/`section`).
  - Cùng model, cùng corpus, cùng Chroma, cosine cho cả 3.

- **≥20 câu:** 21 câu trong `benchmark/questions.json`: 16 dev / 5 test; 5 câu
  có filter (q04, q05, q16 dev + q17, q18 test). Mỗi câu có `evidence_quote`
  trích nguyên văn trong corpus, đã kiểm chứng bằng `validate_benchmark.py`
  (kết quả OK) và `browse_corpus.py find ...` trước khi chạy. Tách dev/test làm
  trước khi chạy thử (benchmark viết xong ngày trước buổi lab, đã commit riêng).

- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** ưu tiên
  **Evidence Hit@3 trên dev**, sau đó xem grounding thủ công, cuối cùng tài
  nguyên (số chunk + thời gian embed).

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 6/16 (37.5%) | 7/16 (43.8%) | 582 | 632.7s | 0 |
| A | test | 3/5 (60%) | 3/5 (60%) | 582 | — | 0 |
| B | dev | 8/16 (50%) | 9/16 (56.3%) | 534 | 623.2s | 0 |
| B | test | 1/5 (20%) | 1/5 (20%) | 534 | — | 0 |
| C | dev | 8/16 (50%) | 9/16 (56.3%) | 534 | 539.7s | 0 |
| C | test | 1/5 (20%) | 1/5 (20%) | 534 | — | 0 |

| Strategy | Coherence TB /2 | Metadata đủ & đúng | Filter tuân thủ | Grounding (0/1/2) — TB /2 |
|---|---|---|---|---|
| A | 0.74 (68 chunk: 0×27, 1×32, 2×9) | 15/15 | N/A (không bật filter) | q21=0, q18=1, q17=q19=q20=2 → 7/10 = 1.4 |
| B | 0.78 (63 chunk: 0×27, 1×23, 2×13) | 15/15 | N/A | q21=0, q18=q19=q20=1, q17=2 → 5/10 = 1.0 |
| C | 0.78 (giống B, cùng chunk) | 15/15 | **2/2** (q17, q18 test) | q21=0, q18=q19=q20=1, q17=2 → 5/10 = 1.0 |

Đường dẫn trace: `results/traces_A.json`, `traces_B.json`, `traces_C.json`
(top-3: chunk id, text, similarity, metadata cho từng câu); số liệu tổng hợp
trong `results/metrics.json` và `chunk_stats.json`. Cách chọn mẫu: coherence
chấm trên 10 trang đầu corpus (PDF 203–212, theo hướng "10 page ID đầu đã
sắp xếp" trong GUIDE), mỗi chunk chứa vị trí đó được chấm theo boundary
đầu/cuối (bắt đầu giữa từ = 0; bắt đầu chữ thường, đọc được nhưng thiếu chủ
thể = 1; đứng một mình hiểu được = 2). Grounding và metadata audit trên 5 câu
test, đọc top-3 của từng cấu hình trong traces và đối chiếu trang trong
`corpus_text.txt`. Người chấm là chính mình (nguy cơ thiên lệch: có xu hướng
cho điểm cao hơn chỗ mình đã viết code — đã cố chấm lại từng nhãn một).

## Phân tích và kết luận

- **So sánh A–B (chunking):** B thắng A trên dev đúng như giả thuyết lúc
  viết log (B 9/16 vs A 7/16), nguyên nhân chính là lỗi "evidence bị cắt
  giữa hai window" của A. Ví dụ: q05/q06/q07 (dev) A trượt còn B lấy đúng
  trang; q03 evidence ~180 ký tự bị hai window 500 của A cắt đôi nên không
  chunk nào chứa đủ, trong khi chunk paragraph của B giữ trọn. A "thắng
  ngược" ở chỗ chi phí: 582 chunk, tổng 271.935 ký tự (chứa ~25% trùng do
  overlap) → embed đắt hơn B (534 chunk, 246.985 ký tự, đúng bằng corpus).
  Nhưng trên **test** B tụt 3/5 → 1/5: 4 câu B trượt (q18, q19, q20, q21)
  có 2 trường hợp top-1 đúng trang (q19 p278:2, q20 p237:2) mà evidence bị
  chunk paragraph cắt đầu câu ("f the operation back to...", "not finish
  the job, the CPU...") — tức lỗi cắt evidence không phải chỉ của A, mà do
  text trích từ PDF tự thân đã có line-break ở giữa câu. q21 cả 3 cấu hình
  đều trả về p251 (mục "security" chung chung) thay vì p291 (mục Reliability
  and Security) — embedding lẫn hai đoạn cùng từ khóa trong cùng chương.
- **So sánh B–C (filter):** Hit@3 y hệt B (0 câu khác nhau) vì 5 câu filter
  vốn đã được trả đúng phạm vi mà không cần filter; filter thể hiện ở độ
  đúng: 2/2 câu test filter, top-3 đều nằm đúng chapter/section. Kết luận
  trên corpus này: metadata filter **không cải thiện retrieval** (vì câu hỏi
  đã nêu phạm vi trong text) nhưng hữu ích để thu hẹp kết quả và audit.
  Giới hạn: chỉ 5 câu có filter, mẫu quá nhỏ để nói chung.
- **2 ví dụ lỗi (có ID):**
  1. **q18 (test, filter chapter 5):** cả A và B/C top-3 đúng p232 nhưng
     evidence "One important distinction between the cache memory and the
     DRAM..." bị tách giữa hai chunk kế nhau (A: p232:3 + p232:4; B/C: p232:3
     bắt đầu bằng "ant distinction...") → tính miss dù filter và page đều
     đúng.
  2. **q21 (test):** top-3 của cả ba cấu hình là p251 (chương 6.1, nói về
     authentication nói chung) thay vì p291 (6.6, nói về enforcement access
     rules) → cùng chương, cùng chủ đề an ninh nhưng khác mục; embedding
     không phân biệt được mức độ cụ thể của câu hỏi.
- **Chiến lược chọn:** theo tiêu chí đã chốt (Hit@3 dev trước), chọn **B
  (paragraph 500, không filter)**. Đánh đổi: B có ít chunk hơn, rẻ hơn A và
  giữ evidence trọn hơn, nhưng chịu rủi ro cắt giữa câu do line-break của
  PDF; C chỉ nên bật khi người dùng thực sự cho phạm vi (chapter/section),
  vì trên corpus này filter gần như vô hại nhưng cũng gần như vô dụng cho
  độ chính xác. Kết luận này chỉ đúng với corpus chương 5–6 OpenStax, không
  suy rộng.
- **Hạn chế:** test chỉ 5 câu → 1 câu lệch là ±20 điểm, kết quả test B/C
  (1/5) có thể không đại diện; coherence chấm theo boundary đầu/cuối nên
  chưa xét ngữ cảnh giữa chunk; HNSW (Chroma) là tìm kiếm xấp xỉ, không
  loại trừ sai khác so với exact; người chấm = người làm bài.
- **Nếu làm lại:** (1) gộp lại các line-wrap trước khi chunk (dùng
  `corpus_text.txt` để nối câu trước khi cắt) để hết lỗi "cắt giữa câu";
  (2) làm test 10+ câu; (3) nếu được phép thì chạy lại cùng pipeline trên
  pgvector exact để loại biến số HNSW; (4) thử hybrid BM25+dense như mục mở
  rộng GUIDE vì câu lỗi q21 kiểu "cùng từ khóa, khác mục" là đối tượng
  keyword retrieval hay cứu.

## Công cụ AI và cách kiểm tra

Dùng Claude (assistant) để viết code pipeline (chunking, embeddings, store,
evaluation, run), tạo corpus_config và bộ câu hỏi; mình tự đọc code và chạy
lại từng bước để xác nhận: (1) `validate_benchmark.py` ra OK trước khi chạy;
(2) kiểm tra chunk cắt evidence bằng cách chạy lại `fixed_size(500,50)` và
`by_paragraph(500)` trên đúng trang gold; (3) chạy lại pipeline 1 lần thấy
số chunk không đổi (582/534/534) — đúng yêu cầu không nhân đôi; (4) nhãn
thủ công trong phần Kết quả là mình tự chấm lại từ traces, không copy từ
output của AI.
