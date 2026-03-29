# CineSense

Hệ thống demo NLP cho bài toán gợi ý phim và phân tích cảm xúc theo khía cạnh (Aspect-Based Sentiment Analysis) trên dữ liệu review tiếng Anh.

Kiến trúc tách lớp rõ ràng: **`ETL → training → runtime API → frontend`**.  
Người chấm có thể:
- Pull code về là chạy ngay demo web (catalog + recommendation + ABSA).
- Xem rõ pipeline xử lý dữ liệu text và các mô hình được dùng trong báo cáo LaTeX.

---

## Kiến trúc & Chức năng chính

- **Data & ETL**
  - Cào dữ liệu từ TMDB API (metadata + poster + full reviews).
  - Chuẩn hóa vào SQL core schema (mặc định SQLite): `core_movies`, `core_reviews`, `core_genres`, `core_movie_genres`.
  - Lọc/nghiền dữ liệu:
    - Heuristic ngôn ngữ để ưu tiên review tiếng Anh.
    - Làm sạch nội dung (trim, giới hạn độ dài, loại review rác).
    - Lưu đủ ngữ cảnh: `author_avatar_url`, `rating`, `source_url`, `source_created_at`, `source`.

- **Training layer (Notebook-first)**
  - Quy ước chính thức: **mọi mô hình dùng runtime phải train trong `Notebook_Report/`**.
  - Artifacts serving được export về:
    - `Notebook_Report/training/artifacts/<artifact_name>/...`
    - `Notebook_Report/absa/artifacts/<artifact_name>/...`
  - Thư mục `training/` chỉ giữ utility/script legacy để tham khảo hoặc thử nghiệm cục bộ, **không phải luồng train chính thức cho demo/chấm điểm**.

- **Runtime API (`api/`)**
  - **Discovery**: `GET /movies`, `GET /movies/{id}` đọc trực tiếp từ database (SQLite mặc định).
  - **Recommendation (artifact-based + hybrid)**:
    - `GET /movies/{id}/similar` → đọc neighbors đã precompute từ artifacts.
    - `GET /recommendations/trending`, `POST /recommendations/search` (thêm `engine`: `"artifact"` hoặc `"hybrid"`).
  - **ABSA**:
    - `POST /absa/analyze` với `{"movie_id": ...}` hoặc `{"text": ...}` trả về danh sách `(aspect, sentiment, score)`.
  - Model được train trong notebook `Notebook_Report/03b_ABSA_AutoLabeling.ipynb` + `Notebook_Report/04_Advanced_ABSA_Modeling.ipynb`.

- **Frontend (`frontend/`)**
  - Trang catalog với phân trang, badge “Has reviews”, rating trung bình.
  - Trang chi tiết phim:
    - Reviews đầy đủ (avatar, rating, nguồn, thời gian).
    - “Similar Movies” (đọc từ recommendation artifacts).
    - Box “Aspect-Based Sentiment” hiển thị bảng aspect–sentiment từ endpoint ABSA.
  - Hero search cho recommendation (search theo vibe, không phải chỉ tên phim).
  - Section “Under the Hood” giải thích rõ chức năng nào gọi model/endpoint nào.

---

## 🛠 Tech Stack

- **Language**: Python 3.10+
- **Backend**: FastAPI
- **Frontend**: HTML/CSS/Vanilla JS
- **Database**: SQLite (`./data/cinesense.db`, `DATABASE_URL`)
- **ML / NLP**:
  - `scikit-learn` (TF‑IDF baseline).
  - `sentence-transformers` (embedding theo `EMBEDDING_MODEL` trong `.env`, mặc định `all-mpnet-base-v2`).
  - Custom ABSA model train từ notebook Kaggle.
- **Dữ liệu**: `scripts/seed_sqlite_from_csv.py` → SQLite `data/cinesense.db`.

---

## 🏗 Project Structure (rút gọn)

```text
CineSen/
├── api/                 # FastAPI app (discovery + recommendation + ABSA)
├── etl_pipeline/        # Crawler TMDB + core schema + config
├── frontend/            # Web UI (catalog + detail + Under the Hood section)
├── training/            # Legacy utilities (không phải luồng train chính thức)
├── infra/seed/          # Ghi chú seed (xem README trong thư mục)
├── scripts/             # Tiện ích (`seed_sqlite_from_csv.py`, test_api, run_backend, ...)
└── Report_For_This_Project/  # Báo cáo LaTeX cho đồ án
```

---

## 🏃 Quick Start (pull về là chạy)

```bash
# 1. Clone & cài đặt
git clone <repo-url> && cd CineSen
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Tạo database SQLite + nạp dữ liệu từ CSV (khớp UUID với artifact gợi ý)
python scripts/seed_sqlite_from_csv.py

# 3. Khởi động Backend (terminal 1)
./scripts/run_backend.sh
# hoặc: uvicorn api.main:app --reload --port 8000

# 4. Khởi động Frontend (terminal 2)
./scripts/run_frontend.sh
# hoặc: cd frontend && python3 -m http.server 3000
```

**Test API (sau khi backend đang chạy):** `python scripts/test_api.py --base-url http://localhost:8000`

> Mặc định `DATABASE_URL=sqlite:///./data/cinesense.db`. Copy `.env.example` → `.env` nếu cần chỉnh TMDB/artifact.

Truy cập: [http://localhost:3000](http://localhost:3000)

> **Lưu ý:**
> - Chạy `python scripts/seed_sqlite_from_csv.py` sau khi có `Notebook_Report/cinesense_*.csv` và `movie_index.json` trong artifact (để UUID khớp gợi ý).
> - Reset dữ liệu: xóa `data/cinesense.db` rồi chạy lại script seed.
> - Recommendation runtime ưu tiên artifacts từ `Notebook_Report/training/artifacts/`.
> - Nếu chưa có artifact phù hợp, runtime fallback theo thứ tự nguồn khả dụng và frontend vẫn có thể quay về catalog chuẩn.

### Huấn luyện mô hình (quy trình chính thức)

```bash
source .venv/bin/activate
# Mở và chạy tuần tự notebook trong Notebook_Report:
# 01_Data_Collection.ipynb
# 02_Data_Preprocessing_EDA.ipynb
# 03_Modeling_Baselines.ipynb
# 03b_ABSA_AutoLabeling.ipynb
# 04_Advanced_ABSA_Modeling.ipynb
# 05_Model_Evaluation.ipynb
# 06_Demo_UseCases.ipynb
```

Checklist export artifact cho runtime nằm tại: `Notebook_Report/README.md`.

### Test API (smoke test)

```bash
# Backend đang chạy: uvicorn api.main:app --port 8000
python scripts/test_api.py --base-url http://localhost:8000
```

- **ABSA:** `POST /absa/analyze` với body `{"text": "..."}` hoặc `{"movie_id": "..."}` trả về bảng aspect–sentiment.

### Tìm kiếm hybrid (`POST /recommendations/search`)

- Trường `engine` (mặc định `"artifact"`): đặt `"hybrid"` để chạy pipeline nhiều tầng giống notebook (`BM25 title` + `genre` + `SBERT` trên `_semantic_text` từ CSV, stage 3 cosine ABSA query vs `absa_movie_profiles.json`).
- **Dữ liệu:** mặc định đọc `Notebook_Report/cleaned_profiles.csv` và file profile ABSA cùng thư mục (xem `PipelineConfig` trong `api/hybrid_search.py`). Checkpoint ABSA dùng `ABSA_ARTIFACT_NAME` (mặc định `absa_distilroberta_latest`) dưới `Notebook_Report/absa/artifacts/...`.
- **Biến môi trường tùy chọn:** `HYBRID_CLEANED_CSV` (đường dẫn file CSV hoặc thư mục), `HYBRID_DATA_DIR`, `HYBRID_CLEANED_BASENAME`.
- **Lần đầu** gọi hybrid có thể chậm (tải SBERT + encode toàn bộ corpus). `POST /recommendations/reload` vừa tải lại artifact gợi ý vừa **xoá cache** pipeline hybrid (lần search hybrid sau sẽ `fit()` lại).
- **Notebook:** `Notebook_Report/hybrid_search_pipeline.py` chỉ re-export `api.hybrid_search`. Mở Jupyter/VS Code với **cwd = thư mục gốc repo** (`CineSen/`) để `import api` hoạt động (ví dụ khi chạy `06_Demo_UseCases.ipynb`).

---
*Dự án đang trong quá trình phát triển bền vững bởi **Vien dep trai**.*
