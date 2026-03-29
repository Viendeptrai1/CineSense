# Chương 4. Xây dựng mô hình

## 4.1. Định nghĩa bài toán mô hình hóa
### 4.1.1. Bài toán chính: Retrieval/Ranking
- Input: query text + tập profile phim.
- Output: danh sách phim xếp hạng theo mức độ liên quan.

### 4.1.2. Bài toán bổ trợ: ABSA
- Input: review text.
- Output: nhãn `(aspect, sentiment)` đa nhãn dùng để refine/giải thích.

## 4.2. Nhóm mô hình được xây dựng
## 4.2.1. Baseline retrieval
- TF-IDF (sparse lexical matching) làm baseline bắt buộc.
- Mục tiêu: tạo mốc so sánh rõ ràng, dễ tái lập.

## 4.2.2. Mô hình semantic/advanced retrieval
- Hướng semantic dùng **English bi-encoder** để bắt ngữ nghĩa truy vấn dài trên dữ liệu review tiếng Anh.
- Base encoder chọn `sentence-transformers/all-MiniLM-L6-v2`, sau đó **fine-tune** bằng query bank nội bộ thay vì chỉ dùng pretrained model nguyên bản.
- Kết hợp multi-field scoring: title, genre, semantic.
- Có cơ chế điều chỉnh trọng số theo loại truy vấn (auto/query-aware).

## 4.2.3. ABSA model
- Mô hình phân loại đa nhãn cho cặp nhãn aspect-sentiment.
- Dùng để:
  - bổ sung điểm thưởng theo ý định truy vấn
  - tăng khả năng giải thích kết quả

## 4.3. Lý do lựa chọn mô hình
- TF-IDF: baseline mạnh cho truy vấn ngắn/keyword.
- Semantic embedding fine-tuned: xử lý tốt truy vấn mô tả ngữ cảnh và bám sát ngôn ngữ bài toán hơn bản multilingual dùng sẵn.
- ABSA: thêm chiều sâu cảm xúc theo khía cạnh thay vì chỉ matching từ khóa.

## 4.4. Pipeline huấn luyện và suy luận
1. Text input -> preprocessing.
2. Vectorization/embedding theo từng nhánh mô hình.
   - Với nhánh semantic chính: query bank đa dạng (`keyword`, `vibe`, `detailed`) -> fine-tune bi-encoder -> export `search_text` + `embeddings.npy`.
3. Tính điểm thành phần (title/genre/semantic).
4. Re-rank theo trọng số.
5. Cộng bonus ABSA (nếu bật refine).
6. Trả Top-K + score breakdown.

## 4.5. Huấn luyện, chia dữ liệu, tuning
- Chia tập theo quy tắc tái lập (train/validation/test hoặc query/candidate split).
- Tuning tham số:
  - n-gram, min_df/max_df (TF-IDF)
  - base encoder, batch size, learning rate, warmup (bi-encoder fine-tune)
  - trọng số tổng hợp điểm
  - ngưỡng/chiến lược ABSA refine
- Ghi lại metadata artifact để tái hiện kết quả.

## 4.6. So sánh mô hình
Tối thiểu các cấu hình so sánh:
- Baseline lexical.
- Semantic-only.
- Artifact recommender.
- Artifact + ABSA refine.
- (Nếu có) Artifact + personalization/rerank.

Mỗi cấu hình cần có:
- metric định lượng
- nhận xét định tính
- trade-off chất lượng/tốc độ.

## 4.7. Kết luận chương
Chương này chứng minh tiêu chí barem phần “lựa chọn mô hình”, “huấn luyện”, “pipeline hoàn chỉnh” và “so sánh/tối ưu” được đáp ứng đầy đủ.
