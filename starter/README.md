# Starter · PostgreSQL + pgvector

Bộ khởi động **tùy chọn** cho lab cá nhân. Docker Compose tạo PostgreSQL + pgvector local; các file trong `src/` là **khung pseudocode có TODO**, chưa đọc tài liệu, tạo embedding, lưu vector hay chạy benchmark. Bạn cần tự hiện thực. Vẫn có thể chọn Qdrant, Chroma hoặc vector store tương đương theo [GUIDE.md](../GUIDE.md).

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf và python-dotenv
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # TODO: đọc / chuẩn hóa tài liệu
│   ├── chunking.py        # TODO: chia chunk
│   ├── embeddings.py      # TODO: chọn model API hoặc local
│   ├── store.py           # TODO: lưu vector, metadata và filter
│   ├── evaluation.py      # TODO: chấm truy xuất, lưu trace
│   └── run.py             # TODO: kết nối các bước thành pipeline
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
└── results/               # lưu kết quả của bạn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Điền key tương ứng trong `.env` nếu dùng OpenRouter, OpenAI hoặc Gemini; **không commit `.env`**. Model local không cần API key. `requirements.txt` chỉ có dependencies cơ bản: tự cài SDK hoặc thư viện local phù hợp với model bạn chọn và ghi lại version/lệnh cài trong báo cáo. Ghi tên model và số chiều; dùng cùng model cho toàn bộ chiến lược và vector query tương thích vector document.

## 3. Hoàn thiện pipeline

1. Đặt corpus vào `data/` hoặc cung cấp manifest/hướng dẫn truy cập. Đọc [GUIDE.md](../GUIDE.md) về **30 trang nội dung**, quyền dữ liệu và metadata.
2. Hoàn thiện từng hàm TODO trong `src/`. Lưu ID tài liệu, nguồn, trang/vị trí và ít nhất một trường filter có ích.
3. Xây ít nhất ba cấu hình; ví dụ A fixed-size, B theo đoạn, C như B nhưng có filter. Cần cùng corpus, model và benchmark; nạp lại không nhân đôi và xử lý chunk cũ khi dữ liệu đổi.
4. Tự viết ít nhất 20 câu hỏi kèm evidence, tách dev/test trước khi thử theo [BENCHMARK.md](../BENCHMARK.md). Lưu trace top-3 và báo cáo đủ năm tiêu chí.
5. Sau khi hoàn thiện, chạy `python -m src.run` từ thư mục `starter/`. Trước khi làm TODO, lệnh này **chủ động báo `NotImplementedError`**.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.

## 4. Bài làm cụ thể (lệnh setup/run của học viên)

Chọn: embedding **local** (`google/embeddinggemma-2`, 768 chiều, chạy CPU)
+ vector store **Chroma local** (không dùng Docker vì máy ở lớp không có
Docker — phương án dự phòng theo CHECKPOINTS.md).

```bash
cd starter
python3 -m venv .venv
# git bash: source .venv/Scripts/activate
python3 -m pip install -r requirements.txt
python3 -m pip install sentence-transformers Pillow torchvision chromadb
# Pillow + torchvision: AutoProcessor của embeddinggemma-2 (model multimodal) cần chúng

cp .env.example .env
# trong .env:
#   EMBEDDING_BACKEND=local
#   EMBEDDING_MODEL=google/embeddinggemma-2
#   VECTOR_STORE=chroma
#   CHROMA_PATH=chroma_data
# (không cần API key nào cả)

# Kiểm tra benchmark trước khi chạy:
python3 scripts/validate_benchmark.py   # phải ra "OK"

# Chạy pipeline 3 cấu hình:
python3 -m src.run
```

Lần đầu chạy, model tải về `~/.cache/huggingface` (cần mạng).
Embed ~534-582 chunk trên CPU mất ~10 phút mỗi cấu hình.

**Sản phẩm trong `results/`:**

| File | Nội dung |
|---|---|
| `metrics.json` | Hit@1 / Evidence Hit@3 theo dev/test cho A, B, C + thời gian embed |
| `chunk_stats.json` | số chunk, độ dài, thời gian, chi phí mỗi cấu hình |
| `traces_A.json`, `traces_B.json`, `traces_C.json` | top-3 đầy đủ (chunk id, text, similarity, metadata) cho từng câu |
| `corpus_text.txt` | text đã chuẩn hóa từng trang (để chấm coherence/grounding thủ công) |

Số liệu dùng trong báo cáo: `report/individual/2A202603623_VoSyThaiSon.md`
(phần Kết quả link đến chính các file trace/metrics trên). Nhãn chấm thủ công
(coherence 10 trang đầu, grounding + metadata audit 5 câu test) được ghi trong
báo cáo, đối chiếu trực tiếp với top-3 trong `traces_*.json`.

Ghi chú: nếu chạy lại với model khác (vd `all-MiniLM-L6-v2`) thì xóa
`chroma_data/` trước (vector khác chiều, không dùng chung được).
