# Báo cáo tóm tắt — CineSen (Notebook Report)

Tài liệu này tóm tắt **bài toán**, **use case**, và **ánh xạ nội dung đồ án** theo **barem** (dạng bảng, dễ đọc). Chi tiết thực nghiệm nằm trong các notebook trong thư mục `Notebook_Report/`.

---

## 1. Bài toán (NLP)

| Mục | Nội dung |
| --- | --- |
| **Tên đề tài** | Gợi ý phim dựa trên **nội dung review** (text), kết hợp phân tích **cảm xúc theo khía cạnh** (ABSA). |
| **Loại bài toán NLP** | (1) **Information Retrieval / Content-based recommendation**: so khớp văn bản (review/overview) để tìm phim tương tự hoặc trả lời truy vấn bằng chữ.<br>(2) **Multi-label classification (ABSA)**: với mỗi đoạn text, dự đoán các cặp **(aspect, sentiment)** trong không gian nhãn cố định. |
| **Dữ liệu** | Review phim (tiếng Anh, nguồn TMDB), metadata phim; có pipeline crawl → CSV → làm sạch → huấn luyện/đánh giá trong notebook. |
| **Mục tiêu hệ thống** | Hỗ trợ người dùng **khám phá phim** bằng ngôn ngữ tự nhiên và hiểu **ý kiến theo khía cạnh** (kịch bản, diễn xuất, hình ảnh, …) để giải thích hoặc tinh chỉnh gợi ý. |

### Input — Output — Phạm vi

| Thành phần | Input | Output | Phạm vi đã làm trong notebook |
| --- | --- | --- | --- |
| **Gợi ý theo text (retrieval)** | Chuỗi văn bản truy vấn; profile văn bản phim (review đã gộp / overview). | Danh sách phim xếp hạng theo độ tương đồng (TF-IDF / Word2Vec). | `03_Modeling_Baselines.ipynb` |
| **ABSA** | Đoạn review (sau tiền xử lý). | Nhãn pseudo **aspect + sentiment**; mô hình BERT-tiny học multi-label. | `03b_ABSA_AutoLabeling.ipynb`, `04_Advanced_ABSA_Modeling.ipynb` |
| **Đánh giá** | Kết quả thực nghiệm đã lưu (JSON). | Bảng metric, biểu đồ, confusion matrix, ví dụ. | `05_Model_Evaluation.ipynb` |

---

## 2. Use case sử dụng (chi tiết)

| STT | Use case | Diễn giải | Thành phần hệ thống chính | Notebook / ghi chú |
| --- | --- | --- | --- | --- |
| **UC1** | **Tìm kiếm phim bằng câu chữ** | Người dùng gõ mô tả sở thích (vd: *“slow burn thriller strong acting”*) và nhận danh sách phim phù hợp. | **Retrieval**: so khớp query với vector hóa profile văn bản phim (TF-IDF / Word2Vec). ABSA **không bắt buộc** cho bước rank đầu; có thể dùng sau để **giải thích** hoặc rerank. | `03_Modeling_Baselines.ipynb` |
| **UC2** | **Trang chi tiết phim — “Phim tương tự”** | Khi xem một phim, hệ thống gợi ý các phim có **review/profile văn bản gần** phim hiện tại. | Cùng pipeline retrieval với **đại diện văn bản phim** (vd: `review_profile` / profile đã merge). | `02` (tạo profile), `03` |
| **UC3** | **Tóm tắt ý kiến theo khía cạnh** | Hiển thị xu hướng: khen/chê theo *script, acting, visuals, …* (từ review hoặc từ mô hình ABSA). | **ABSA** (pseudo-label + model); có thể tổng hợp theo phim. | `03b`, `04` |
| **UC4** | **Lọc / ưu tiên theo khía cạnh** (mở rộng) | Người dùng quan tâm “hình ảnh” hơn “nhịp phim” → rerank hoặc lọc ứng viên sau retrieval. | Cần tín hiệu **aspect** (từ ABSA hoặc rule). | Thiết kế use case; thực nghiệm cốt lõi trong `03b`, `04` |
| **UC5** | **Giải thích gợi ý** (mở rộng) | “Vì sao phim này được gợi ý?” — trích khía cạnh / đoạn review liên quan. | ABSA + trích dẫn text. | `04`, `05` (ví dụ dự đoán) |

---

## 3. Thứ tự chạy notebook (đề xuất)

| Thứ tự | Notebook | Mục đích |
| --- | --- | --- |
| 1 | `01_Data_Collection.ipynb` | Thu thập dữ liệu (crawl TMDB) → `cinesense_movies.csv`, `cinesense_reviews.csv` |
| 2 | `02_Data_Preprocessing_EDA.ipynb` | Làm sạch, tạo profile, EDA → `cleaned_profiles.csv`, `absa_clean_reviews.csv` |
| 3 | `03_Modeling_Baselines.ipynb` | Baseline gợi ý (TF-IDF, Word2Vec), đánh giá IR → `eval_results.json` |
| 4 | `03b_ABSA_AutoLabeling.ipynb` | Pseudo-label ABSA → `absa/absa_unlabeled.jsonl`, `absa/labeled_absa_auto.jsonl` |
| 5 | `04_Advanced_ABSA_Modeling.ipynb` | Huấn luyện ABSA (BERT-tiny), xuất `absa/absa_eval.json` |
| 6 | `05_Model_Evaluation.ipynb` | Tổng hợp đánh giá recommendation + ABSA |

---

## 4. Ánh xạ theo BAREM (10 điểm)

Dưới đây là **cùng cấu trúc barem**, kèm **chỗ trình bày trong đồ án / notebook** (để bạn bảo vệ và viết báo cáo LaTeX/PDF).

### 4.1. Mức độ hoàn thiện đề tài — 1.5 điểm

| Nội dung (barem) | Mô tả yêu cầu | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Xác định đúng bài toán NLP | Task rõ: classification, retrieval, … | 0.5 | **Retrieval** (gợi ý phim theo text) + **ABSA** multi-label (aspect × sentiment). |
| Phân tích yêu cầu | Mục tiêu, input/output, phạm vi | 0.5 | Mục **§1** và **§2** trong file này; chi tiết trong notebook `01`–`04`. |
| Thu thập & mô tả dữ liệu | Nguồn, ngôn ngữ, quy mô | 0.5 | `01` (crawl), `02` (EDA: phân bố độ dài, genre, rating, từ). |

### 4.2. Cơ sở lý thuyết — 1.0 điểm

| Nội dung (barem) | Yêu cầu | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Kiến thức NLP cơ bản | Tokenization, embedding, … | 0.5 | TF-IDF, Word2Vec, tokenization trong `02`/`03`; ABSA = multi-label trên encoder. |
| Thuật toán / mô hình chính | Giải thích đúng mô hình | 0.5 | **Cosine similarity** (retrieval); **BERT-tiny + sigmoid + BCE** (ABSA) trong `04`. |

### 4.3. Tiền xử lý dữ liệu — 1.5 điểm

| Nội dung (barem) | Mô tả | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Làm sạch dữ liệu | Lowercase, URL, punctuation, emoji | 0.5 | Hàm `clean_text` trong `02`; export `absa_clean_reviews.csv` cho `03b`. |
| Xử lý ngôn ngữ | Tokenization, stopword, … | 0.5 | Tokenization đơn giản (EDA) trong `02`; review tiếng Anh. |
| Trực quan dữ liệu | Độ dài câu, phân bố lớp, word frequency | 0.5 | Các biểu đồ EDA trong `02`. |

### 4.4. Xây dựng mô hình — 2.5 điểm

| Nội dung (barem) | Yêu cầu | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Lựa chọn mô hình phù hợp | Baseline ML / DL | 0.5 | TF-IDF, Word2Vec (`03`); Transformer nhẹ (`04`). |
| Huấn luyện mô hình | Train/val, loss, optimizer | 1.0 | `03`: split + grid; `04`: train/val, BCE, AdamW, micro/macro F1. |
| Pipeline hoàn chỉnh | text → preprocess → vector/model → output | 0.5 | Chuỗi `01`→`02`→`03`/`03b`→`04`→`05`. |
| Tối ưu / so sánh | So sánh phương pháp | 0.5 | **Grid search** TF-IDF/Word2Vec trong `03`; so sánh NDCG trong `05`. |

### 4.5. Đánh giá & thực nghiệm — 1.5 điểm

| Nội dung (barem) | Yêu cầu | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Chỉ số định lượng | Metric phù hợp task | 0.5 | **Precision@K, Recall@K, NDCG@K** (`03`, `05`); **micro/macro F1** ABSA (`04`, `05`). |
| Minh họa trực quan | Confusion matrix, bảng so sánh, ví dụ | 0.5 | `05`: bảng model, bar chart, confusion (retrieval + ABSA overall), ví dụ dự đoán. |
| Thảo luận kết quả | Ý nghĩa, hạn chế, hướng cải thiện | 0.5 | Template gợi ý trong `05`; nhấn mạnh **weak label** (genre / pseudo ABSA). |

### 4.6. Ứng dụng demo — 1.0 điểm

| Hạng mục (barem) | Yêu cầu | Điểm | Trình bày trong đồ án CineSen |
| --- | --- | --- | --- |
| Demo chạy được | Web/desktop/mobile | 0.5 | **API / web demo** trong repo chính (ngoài thư mục notebook này). |
| Giao diện & trải nghiệm | Input/Output rõ ràng | 0.25 | Mô tả form tìm kiếm, danh sách phim (báo cáo chính / slide). |
| Tính hữu ích thực tế | Kịch bản sử dụng | 0.25 | **§2** (use case) trong file này. |

### 4.7. Báo cáo & bảo vệ — 1.0 điểm

| Nội dung (barem) | Yêu cầu | Điểm | Gợi ý |
| --- | --- | --- | --- |
| Báo cáo đúng chuẩn | Giới thiệu, phương pháp, thực nghiệm, hình bảng, tài liệu tham khảo | 0.5 | Dùng **§1–§4** làm khung; chèn hình từ `02`/`05`. |
| Thuyết trình, trả lời câu hỏi | Hiểu hệ thống, không đọc slide | 0.5 | Ôn pipeline **§3** + hạn chế **pseudo-label** và **weak relevance** trong `03`. |

---

## 5. Ghi chú quan trọng (khi viết báo cáo dài)

| Chủ đề | Nội dung cần nói rõ |
| --- | --- |
| **Nhãn gợi ý phim (retrieval)** | Có thể dùng **weak supervision** (vd: overlap thể loại) để tính Precision@K / NDCG — giải thích trong `03`/`05`. |
| **Nhãn ABSA** | **Pseudo-label** (keyword + lexicon trong `03b`) — không phải gold; nêu hạn chế và hướng gán nhãn tay / mô hình mạnh hơn. |
| **ABSA vs gợi ý phim** | ABSA bổ sung **giải thích / tín hiệu khía cạnh**; **rank** chính vẫn là retrieval baseline trong `03`. |

---

*Tài liệu này tương thích với `Barem.md` trong cùng thư mục; cập nhật khi bạn thay đổi notebook hoặc metric.*
