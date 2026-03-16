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
  - Chuẩn hóa vào PostgreSQL core schema: `core_movies`, `core_reviews`, `core_genres`, `core_movie_genres`.
  - Lọc/nghiền dữ liệu:
    - Heuristic ngôn ngữ để ưu tiên review tiếng Anh.
    - Làm sạch nội dung (trim, giới hạn độ dài, loại review rác).
    - Lưu đủ ngữ cảnh: `author_avatar_url`, `rating`, `source_url`, `source_created_at`, `source`.

- **Training layer (`training/`)**
  - Xây dựng “movie profile” (title + overview + genres + review snippets).
  - **Baseline TF‑IDF**: `training/baselines/train_tfidf.py` (sparse vectors + cosine similarity).
  - **Sentence Transformer**: `training/models/train_sentence_transformer.py`
    - Dùng encoder `sentence-transformers/all-mpnet-base-v2` (768‑dim, English) hoặc model cấu hình trong `etl_pipeline/config.py`.
  - Sinh artifacts cho serving:
    - `movie_index.json`, `similar_by_movie.json`, ma trận TF‑IDF / embeddings, `splits.json`, `metadata.json`, `eval.json`.

- **Runtime API (`api/`)**
  - **Discovery**: `GET /movies`, `GET /movies/{id}` đọc trực tiếp từ PostgreSQL core schema.
  - **Recommendation (artifact-based)**:
    - `GET /movies/{id}/similar` → đọc neighbors đã precompute từ artifacts.
    - `GET /recommendations/trending`, `POST /recommendations/search`.
  - **ABSA**:
    - `POST /absa/analyze` với `{"movie_id": ...}` hoặc `{"text": ...}` trả về danh sách `(aspect, sentiment, score)`.
    - Model được train từ notebook `notebooks/kaggle_absa_train.ipynb` trên dữ liệu trong `training/data/absa/`.

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
- **Database**: PostgreSQL (core schema cho ML)
- **ML / NLP**:
  - `scikit-learn` (TF‑IDF baseline).
  - `sentence-transformers` (Sentence-BERT, mặc định `all-mpnet-base-v2`).
  - Custom ABSA model train từ notebook Kaggle.
- **Infra**: Docker & Docker Compose (seed toàn bộ database qua `infra/seed/postgres/01-seed-data.sql.gz`).

---

## 🏗 Project Structure (rút gọn)

```text
CineSen/
├── api/                 # FastAPI app (discovery + recommendation + ABSA)
├── etl_pipeline/        # Crawler TMDB + core schema + config
├── frontend/            # Web UI (catalog + detail + Under the Hood section)
├── training/            # Offline training (TF‑IDF, Sentence-BERT, evaluation)
├── infra/               # Docker & database seeds
│   └── seed/postgres/   # 01-seed-data.sql.gz (4 900 movies, 9 373 reviews)
├── scripts/             # Tiện ích (test_api, run_backend, run_frontend, ...)
└── Report_For_This_Project/  # Báo cáo LaTeX cho đồ án
```

---

## 🏃 Quick Start (pull về là chạy)

```bash
# 1. Clone & cài đặt
git clone <repo-url> && cd CineSen
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Khởi động database (PostgreSQL tự seed 4 900 phim + 9 373 reviews)
docker-compose up -d
# Lần đầu Postgres detect volume trống → tự nạp infra/seed/postgres/01-seed-data.sql.gz
# Chờ ~30s để seed xong, kiểm tra: docker logs cinesense-postgres --tail 5

# 3. Khởi động Backend (terminal 1)
./scripts/run_backend.sh
# hoặc: uvicorn api.main:app --reload --port 8000

# 4. Khởi động Frontend (terminal 2)
./scripts/run_frontend.sh
# hoặc: cd frontend && python3 -m http.server 3000
```

**Test API (sau khi backend đang chạy):** `python scripts/test_api.py --base-url http://localhost:8000`

> Không cần file `.env` để chạy app -- mọi config đã có default. Chỉ cần tạo `.env` khi muốn cào thêm data mới (cần `TMDB_API_KEY`).

Truy cập: [http://localhost:3000](http://localhost:3000)

> **Lưu ý:**
> - Lần đầu `docker-compose up -d` sẽ tự tạo database và nạp toàn bộ dữ liệu đã cào (4 900 phim, 9 373 reviews, 19 genres). Không cần chạy thêm script gì.
> - Nếu muốn reset database: `docker-compose down -v` rồi `docker-compose up -d`.
> - Recommendation runtime đọc artifacts từ `training/artifacts/`. Nếu chưa có, frontend tự fallback về catalog chuẩn.

### Build training artifacts (optional)

```bash
source .venv/bin/activate
# Similarity / recommender (English encoder)
python -m training.baselines.train_tfidf --artifact-name tfidf_latest --top-k 20
python -m training.models.train_sentence_transformer --artifact-name sbert_en_latest --top-k 20
# ABSA (Aspect-Based Sentiment Analysis)
python -m training.data.absa_prepare --output training/data/absa/absa_unlabeled.jsonl --limit 500
# Sau khi gán nhãn file labeled_absa.jsonl:
python -m training.models.absa_model --labeled training/data/absa/labeled_absa.jsonl --artifact-dir training/artifacts/absa_latest
# Hoặc dùng demo labeled: python -m training.models.absa_model --labeled training/data/absa/labeled_absa_demo.jsonl
# Train ABSA trên Kaggle (GPU): dùng notebook notebooks/kaggle_absa_train.ipynb — upload labeled JSONL làm dataset, bật GPU, Run All.
```

### Test API (smoke test)

```bash
# Backend đang chạy: uvicorn api.main:app --port 8000
python scripts/test_api.py --base-url http://localhost:8000
```

- **Semantic search:** query tiếng Anh qua endpoint search (khi Qdrant đã cấu hình).
- **ABSA:** `POST /absa/analyze` với body `{"text": "..."}` hoặc `{"movie_id": "..."}` trả về bảng aspect–sentiment.

---
*Dự án đang trong quá trình phát triển bền vững bởi **Vien dep trai**. 🎬✨*
