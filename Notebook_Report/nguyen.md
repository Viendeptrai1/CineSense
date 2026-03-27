# Implementation Plan: Cấu Trúc Khuyên Dùng Cho Hệ Thống Gợi Ý Cá Nhân Hóa (ABSA)

Tài liệu này là bản Tóm tắt Kế hoạch Thực thi (Blueprint). Rất phù hợp để bạn đưa thẳng vào Chương "Thiết kế Kiến trúc Hệ thống" (System Design) trong Đồ án.

## Giai đoạn 1: Chuẩn bị Cơ sở Dữ liệu (Database Schema Update)

Hệ thống hiện tại chỉ lưu review kéo từ website khác (TMDB). Để làm "Cá nhân hóa", chúng ta bắt buộc phải có Dữ liệu của người dùng nội bộ.

### Cần thêm 2 bảng mới trong PostgreSQL:
1. Bảng `user_reviews`:
   - [id](file:///d:/CODE/Natural%20Language%20Processing/CineSense-main/training/baselines/train_tfidf.py#36-108) (UUID), `user_id` (UUID), `movie_id` (UUID)
   - [content](file:///d:/CODE/Natural%20Language%20Processing/CineSense-main/etl_pipeline/db_postgres.py#289-295) (Text): Nội dung review do chính User này gõ vào web của bạn.
   - `created_at` (Timestamp).
2. Bảng `absa_user_profiles` (Lưu Gu của User):
   - `user_id` (UUID - Khóa chính)
   - `profile_vector` (JSONB hoặc Array): Chứa tỷ lệ điểm số 7 khía cạnh (Script, Acting...).
   - `last_updated` (Timestamp).

---

## Giai đoạn 2: Xây dựng Pipeline Phân tích Động (Offline Processing)

Vì model RoBERTa khá nặng, chúng ta không chạy nó mỗi khi user bấm tìm phim. Quá trình tạo "Gu" phải được chạy ngầm (Offline Batch Job).

### Bước 2A: Sinh "Hồ sơ Phim" (Movie ABSA Profile)
- **Schedule:** Chạy mỗi đêm lúc 12h.
- **Input:** Lấy TẤT CẢ reviews của `Movie X` (cả từ TMDB lẫn nội bộ).
- **Process:** Chạy qua [AbsaClassifier](file:///d:/CODE/Natural%20Language%20Processing/CineSense-main/training/models/absa_model.py#79-112).
- **Output:** Tính trung bình (Average) để ra 1 Vector tỷ lệ phần trăm.
  *Ví dụ xuất ra: `Movie X = { acting: 0.9, visuals: 0.8, script: 0.4 }`.*
- **Lưu trữ:** Ghi đè file `artifacts/absa_movie_profiles.json`.

### Bước 2B: Sinh "Hồ sơ Gu Người dùng" (User ABSA Profile)
- **Schedule:** Chạy mỗi khi User vừa đăng xong 1 review mới, hoặc chạy đồng bộ mỗi đêm.
- **Input:** Lấy TẤT CẢ reviews mà `User A` đã từng viết trên Web từ trước tới nay.
- **Process:** Chạy qua [AbsaClassifier](file:///d:/CODE/Natural%20Language%20Processing/CineSense-main/training/models/absa_model.py#79-112) để dịch nghĩa xem ông A này hay Khen điều gì và hay Chê điều gì.
- **Output:** Tính trung bình có trọng số (Weighted Average - Ưu tiên các review mới viết gần đây).
  *Ví dụ xuất ra: `User A = { acting_preference: 0.85, visual_preference: 0.3 }`.*
- **Lưu trữ:** Ghi vào bảng `absa_user_profiles`.

---

## Giai đoạn 3: Thuật toán Cốt lõi Kép (Dual-Pathway Matching Algorithm)

Thuật toán cấu thành từ 2 luồng (viết trong `api/personalized_recommender.py`), đảm bảo vừa bám sát sở thích cá nhân, vừa mang tính khám phá cộng đồng.

### Luồng 1: Khớp Gu Cá Nhân (Content-Based ABSA Matching)
1. Lấy `Vector Gu của User A` (Từ Database).
2. Tính khoảng cách **Cosine Similarity** với `10,000 Vector Hồ sơ Phim` (Từ JSON Artifacts).
   - *Mục đích: Phim nào có Đặc trưng (Khen chê Diễn xuất/Kịch bản) trùng khớp nhất với Gu của A sẽ được điểm cao.*
   - Kết quả: Danh sách `List_1` với `Score_1`.

### Luồng 2: Khớp Gu Cộng Đồng (User-Based Collaborative Filtering)
1. Lấy `Vector Gu của User A` mang đi so sánh **Cosine Similarity** với `Tất cả Vector Gu của các Users khác` trong Database.
2. Tìm ra Top 5 "Tri kỷ" (Những người dùng B, C, D... có Gu giống A nhất).
3. Lấy ra những bộ phim mà hội "Tri kỷ" này đã xem và chấm điểm cao, nhưng **A chưa từng xem**.
   - *Mục đích: Mở rộng tầm nhìn, gợi ý những phim bất ngờ mà A có thể thích dựa trên hội nhóm cùng khẩu vị.*
   - Kết quả: Danh sách `List_2` với `Score_2`.

### Dung hợp kết quả (Hybrid Fusion)
Gộp danh sách `List_1` và `List_2` lại. Tính điểm tổng theo công thức:
> `Final_Score(Movie_X)` = [(α × Score_1) + (β × Score_2)](file:///d:/CODE/Natural%20Language%20Processing/CineSense-main/api/recommender.py#33-58)

*(Ví dụ: α = 0.6 và β = 0.4)*. Cuối cùng sắp xếp danh sách (Sort desc) để lấy ra **Top 10 phim** hoàn hảo nhất cho User A.

---

## Giai đoạn 4: Trị dứt điểm "Bài toán Khởi động lạnh" (Cold-Start Problem)

Giải pháp "Onboarding UI" (Chỉ áp dụng cho New Users chưa viết Review nào).

### Kịch bản UI trên Frontend:
- Người dùng lần đầu đăng ký thành viên. Màn hình chào mừng (Pop-up) hiện ra:
  **"Chào mừng đến với CineSense. Để chúng tôi hiểu bạn hơn, bạn thường để tâm đến điều gì nhất khi ra rạp phim?"**
  - [ ] Kịch bản lắt léo (Script)
  - [ ] Diễn viên diễn xuất đỉnh cao (Acting)
  - [ ] Kỹ xảo cháy nổ mãn nhãn (Visuals)
  - [ ] Nhạc phim nổi da gà (Music)
- Nếu user tick chọn "Diễn xuất" & "Kịch bản" -> Dưới Backend tự động fake (khởi tạo ảo) một `absa_user_profiles` cơ sở: `{ acting: 0.9, script: 0.9, visuals: 0.5, ...}`.
- Nhờ bước đệm thông minh này, ngay trong lần lướt Web đầu tiên, User mới toanh đã nhận được danh sách Gợi ý chuẩn xác mà không cần đợi vài tháng để thu thập lịch sử Review.

---

## Giai đoạn 5: Tích hợp API và Giao diện (The Final Touch)

Thiết kế điểm nối (Endpoint) và làm Trí tuệ Nhân tạo có thể giải thích được (XAI).

### 5.1. Thiết kế Endpoint (api/routes/users.py)
```python
GET /users/{user_id}/recommendations
```
**Trả về (JSON Response):**
```json
{
  "recommended_movies": [
    {
      "movie_id": "123-abc",
      "title": "Inception",
      "match_score": 0.96,
      "explain_reason": "Because you love exceptional Script and Visuals"
    }
  ]
}
```

### 5.2. Giao diện (Frontend)
Tạo một Tab hoàn toàn mới trên Navbar tên là **"For You" (Dành Riêng Cho Bạn)**.
Phía dưới mỗi Poster phim gợi ý ra, in rõ ràng dòng nhãn (Badge):
> 💡 *Trùng khớp 96% với Gu thưởng thức Kịch bản của bạn.*

Đến đây, Hệ thống của bạn chính là một nền tảng Giải trí cực kỳ Thấu hiểu người dùng.
