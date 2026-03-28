# Chương 3. Tiền xử lý dữ liệu và EDA

## 3.1. Mục tiêu tiền xử lý
- Chuẩn hóa văn bản để giảm nhiễu trước vectorization/ranking.
- Bảo toàn tín hiệu ngữ nghĩa quan trọng cho truy vấn gợi ý phim.

## 3.2. Làm sạch dữ liệu văn bản
Các bước chính (theo notebook preprocessing):
- Lowercase toàn bộ text.
- Loại URL, email, mention/hashtag.
- Loại HTML tags.
- Loại emoji/ký tự đặc biệt không cần thiết.
- Chuẩn hóa khoảng trắng.

Kết quả: văn bản đồng nhất hơn, giảm token rác, cải thiện ổn định cho TF-IDF/semantic embedding.

## 3.3. Xử lý ngôn ngữ
- Tokenization ở mức từ (phù hợp bài toán retrieval).
- Stopword handling cho thống kê từ vựng và vector hóa.
- Tạo profile phim từ nhiều nguồn text:
  - title
  - overview
  - genres
  - review snippets

## 3.4. Xây dựng đặc trưng văn bản cho mô hình
- `movie_profile`: biểu diễn tổng hợp để phục vụ retrieval.
- `review_profile`: tập trung vào nội dung review cho bài toán chính.
- Biến thể profile hỗ trợ so sánh mô hình ở chương sau.

## 3.5. Phân tích khám phá dữ liệu (EDA)
Các nhóm biểu đồ cần có trong báo cáo:
- Phân bố độ dài văn bản (token length distribution).
- Phân bố số review/phim.
- Top genres theo số lượng.
- Top word frequency trên review profile.
- (Nếu có) phân bố rating.

## 3.6. Ý nghĩa EDA đối với thiết kế mô hình
- Chọn phương pháp vector hóa phù hợp độ dài văn bản.
- Nhận diện mất cân bằng dữ liệu theo nhóm nội dung.
- Xác định lý do cần kết hợp lexical + semantic thay vì chỉ một hướng.

## 3.7. Kết quả đầu ra sau preprocessing
- `cleaned_profiles.csv`
- `absa_clean_reviews.csv`

Các đầu ra này là đầu vào trực tiếp cho các notebook modeling/evaluation tiếp theo.
