# CineSense

CineSense hiện đang chạy ở chế độ `discovery-only`: frontend chỉ hiển thị toàn bộ phim có trong PostgreSQL với phân trang. Search và vector serving đang được tắt tạm thời để ưu tiên làm sạch lại dữ liệu tiếng Anh trong Postgres, chuẩn bị cho pipeline embedding và recommendation ở giai đoạn tiếp theo.

## Trạng thái hiện tại

- Frontend: một trang catalog phân trang từ PostgreSQL
- Backend: FastAPI chỉ phục vụ discovery runtime
- ETL: ưu tiên nạp metadata/review tiếng Anh vào Postgres core schema
- Qdrant / semantic search: tạm tắt khỏi runtime hiện tại

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
*   **AI:** `sentence-transformers` (paraphrase-multilingual-MiniLM-L12-v2)
*   **Infra:** Docker & Docker Compose.

---

## 🏗 Project Structure
```text
CineSen/
├── api/                # FastAPI application
├── etl_pipeline/       # Crawler & Vectorization scripts
├── frontend/           # Web interface
├── infra/              # Docker setup & Data seeds
│   └── seed/           # Portable data snapshots for collaborators
├── scripts/            # Utility scripts (backup/restore)
└── docker-compose.yml  # Container orchestration
```

---

## 🏃 Hướng dẫn chạy ứng dụng (Quick Start)

Để khởi động toàn bộ hệ thống CineSense hiện tại, bạn thực hiện 3 bước sau:

1.  **Khởi động Cơ sở dữ liệu:**
    ```bash
    docker-compose up -d
    ```
2.  **Khởi động Backend (API):**
    ```bash
    source .venv/bin/activate
    uvicorn api.main:app --reload --port 8000
    ```
3.  **Khởi động Frontend (Giao diện):**
    ```bash
    cd frontend
    python3 -m http.server 3000
    ```
Sau đó truy cập địa chỉ: [http://localhost:3000](http://localhost:3000)

Lưu ý:
- Discovery page hiện không có search box hoạt động
- Nguồn dữ liệu runtime là PostgreSQL core schema
- Semantic search sẽ được nối lại sau khi pipeline embedding mới hoàn tất

---

## ⚙️ Cài đặt bổ sung (Dành cho Dev)
Nếu bạn vừa pull code về và thấy web rỗng, hãy khôi phục dữ liệu mẫu:
```bash
python scripts/restore_data.py
```

---
*Dự án đang trong quá trình phát triển bền vững bởi **Vien dep trai**. 🎬✨*
