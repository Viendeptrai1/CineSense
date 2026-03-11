# CineSense

CineSense hiện chạy theo kiến trúc tách lớp rõ ràng: `ETL -> training -> runtime API -> frontend`.
Frontend vẫn ưu tiên discovery catalog từ PostgreSQL, đồng thời có thể bật recommendation dựa trên artifacts được sinh từ thư mục `training/`.

## Trạng thái hiện tại

- Frontend: catalog + detail + recommendation search (artifact-based fallback)
- Backend: FastAPI phục vụ discovery và recommendation endpoints
- ETL: nạp metadata/review tiếng Anh vào Postgres core schema
- Training: mô hình baseline/improved nằm trong `training/`

---

## 🚀 Roadmap (Chuẩn AI Engineer)

### 🟢 Giai đoạn 1: Data & ETL (Hoàn thiện Data Engine) 🛠️
*   **Việc:** Xây dựng Pipeline ETL tự động và chuẩn hóa tri thức phim.
    *   Cào dữ liệu từ TMDB API: Metadata, Poster và đặc biệt là **Movie Reviews** (nguồn tri thức chính).
    *   **Text Processing & Embeddings:** Sử dụng mô hình Language Model (LM) `paraphrase-multilingual-MiniLM-L12-v2` để chuyển hóa toàn bộ nội dung text thành không gian vector 384 chiều.
    *   **Vector Database:** Kiến trúc hóa Qdrant để lưu trữ hàng triệu vector review, hỗ trợ truy vấn ngữ thực tế nhanh dưới 100ms.

### 🟢 Giai đoạn 2: AI Backend & Semantic Search 🧠
*   **Việc:** Xây dựng lõi xử lý ngôn ngữ tự nhiên (NLP Core).
    *   **Query Vectorization:** Biến đổi câu hỏi tự nhiên của người dùng thành "tọa độ" trong không gian vector thông qua LM.
    *   **Semantic Matching:** Thay vì so khớp từ khóa (Keyword matching), hệ thống sử dụng **Cosine Similarity** để tìm các bộ phim có sự tương đồng về ngữ cảnh và cảm xúc (vibe).
    *   **Ranking Logic:** Phát triển thuật toán xếp hạng kết quả dựa trên cả điểm số vector và metadata (rating, popularity).

### 🟡 Giai đoạn 3: Frontend Integration & Cold Start 🎨
*   **Việc:** Xây dựng giao diện Web và xử lý trải nghiệm AI.
    *   Trang Home hiển thị danh sách phim đề xuất thông minh.
    *   Hệ thống đánh giá phim (Rating system) 10 sao đồng bộ trực tiếp vào cơ sở dữ liệu.
    *   **Cold Start Handling:** Thiết kế cơ chế gợi ý mặc định khi người dùng chưa cung cấp query để đảm bảo app luôn có nội dung phong phú.

### 🔴 Giai đoạn 4: Custom AI Models & Manual Training 🚀
*   **Việc:** Tự xây dựng và huấn luyện (Train from scratch) các mô hình gợi ý chuyên sâu.
    *   **Custom Recommender Models:** Thiết kế và code thủ công các mô hình gợi ý dựa trên cộng tác (Collaborative Filtering) kết hợp với dựa trên nội dung (Content-based) sử dụng các kiến trúc Neural Network (Autoencoders, Matrix Factorization).
    *   **Language Model Fine-tuning:** Huấn luyện lại các mô hình LM (như BERT, RoBERTa hoặc GPT-based) trên tập ngữ liệu Review phim của người Việt để hiểu sâu các từ lóng, thuật ngữ chuyên môn về điện ảnh.
    *   **Hybrid Reranking:** Kết hợp các mô hình thống kê và mô hình AI để tinh chỉnh thứ tự gợi ý cuối cùng, đảm bảo tính cá nhân hóa (Personalization) cao nhất.

---

## 🎬 Ứng dụng thực tế (Use Cases)

Dự án này không chỉ dừng lại ở việc "gợi ý phim" đơn thuần mà hướng tới giải quyết các bài toán thực tế của ngành giải trí:

1.  **Tìm kiếm theo ngữ cảnh (Semantic Search Bar):**
    *   Thay vì chỉ tìm theo tên phim (từ khóa chính xác), người dùng có thể tìm theo cảm giác: *"Phim buồn xem vào ngày mưa"*, *"Phim kinh dị không có jumpscare"*. Đây là điểm vượt trội mà các web phim truyền thống vẫn chưa làm tốt.
2.  **Chatbot tư vấn phim (AI Concierge):**
    *   Tích hợp vào các nền tảng như Messenger/Discord. Chatbot đóng vai một người bạn "mọt phim", thấu hiểu gu của user và truy vấn nhanh từ "trí nhớ" (Vector DB) để đưa ra lời khuyên tức thì.
3.  **Công cụ cho Content Creator/Reviewer:**
    *   Hỗ trợ các kênh review phim tìm kiếm các bộ phim *underrated* (ít người biết) nhưng có nội dung và cảm xúc tương đồng với các bom tấn để giới thiệu cho khán giả, tạo ra nội dung mới lạ và chất lượng.

---

## 🛠 Tech Stack
*   **Language:** Python 3.10+
*   **Framework:** FastAPI (Backend), Vanilla JS/HTML/Next.js (Frontend)
*   **Databases:**
    *   **PostgreSQL:** Lưu trữ thông tin phim, người dùng, đánh giá.
    *   **Qdrant:** Vector database lưu trữ và tìm kiếm vector review phim.
*   **AI:** `sentence-transformers` (paraphrase-multilingual-MiniLM-L12-v2, 384 dims)
*   **Infra:** Docker & Docker Compose.

---

## 🏗 Project Structure
```text
CineSen/
├── api/                # FastAPI application
├── etl_pipeline/       # Crawler & Vectorization scripts
├── frontend/           # Web interface
├── training/           # Offline model training & artifact export
├── infra/              # Docker setup & Data seeds
│   └── seed/           # Portable data snapshots for collaborators
├── scripts/            # Utility scripts (backup/restore)
└── docker-compose.yml  # Container orchestration
```

---

## 🏃 Quick Start (Pull về là chạy)

```bash
# 1. Clone & cài đặt
git clone <repo-url> && cd CineSen
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Khởi động database (PostgreSQL tự seed 4 900 phim + 9 373 reviews)
docker-compose up -d
# Lần đầu Postgres detect volume trống → tự nạp infra/seed/postgres/01-seed-data.sql.gz
# Chờ ~30s để seed xong, kiểm tra: docker logs cinesense-postgres --tail 5

# 3. Khởi động Backend
uvicorn api.main:app --reload --port 8000

# 4. Khởi động Frontend
cd frontend && python3 -m http.server 3000
```

> Không cần file `.env` để chạy app -- mọi config đã có default. Chỉ cần tạo `.env` khi muốn cào thêm data mới (cần `TMDB_API_KEY`).

Truy cập: [http://localhost:3000](http://localhost:3000)

> **Lưu ý:**
> - Lần đầu `docker-compose up -d` sẽ tự tạo database và nạp toàn bộ dữ liệu đã cào (4 900 phim, 9 373 reviews, 19 genres). Không cần chạy thêm script gì.
> - Nếu muốn reset database: `docker-compose down -v` rồi `docker-compose up -d`.
> - Recommendation runtime đọc artifacts từ `training/artifacts/`. Nếu chưa có, frontend tự fallback về catalog chuẩn.

### Build training artifacts (optional)

```bash
source .venv/bin/activate
python scripts/audit_core_data.py --output-json training/artifacts/latest/core_audit.json
python -m training.baselines.train_tfidf --artifact-name tfidf_latest --top-k 20
python -m training.models.train_sentence_transformer --artifact-name sbert_latest --top-k 20
python -m training.evaluation.run_eval --artifact-dir training/artifacts/sbert_latest --output-json training/artifacts/sbert_latest/eval.json
```

---
*Dự án đang trong quá trình phát triển bền vững bởi **Vien dep trai**. 🎬✨*
