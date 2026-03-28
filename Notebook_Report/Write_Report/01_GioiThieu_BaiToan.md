# Chương 1. Giới thiệu đề tài và xác định bài toán NLP

## 1.1. Bối cảnh và tính cấp thiết
Trong bối cảnh kho phim số tăng nhanh, người dùng thường gặp khó khăn khi tìm phim phù hợp sở thích thật sự nếu chỉ dựa vào metadata ngắn (thể loại, năm phát hành, điểm trung bình). Review text chứa thông tin giàu ngữ nghĩa hơn (cảm nhận về kịch bản, diễn xuất, nhịp phim, bầu không khí), vì vậy khai thác review bằng NLP giúp hệ gợi ý phản ánh đúng nhu cầu người xem hơn.

## 1.2. Vấn đề cần giải quyết
Hệ thống cần trả lời các truy vấn tự nhiên như:
- truy vấn ngắn theo từ khóa: `crime thriller`
- truy vấn ngữ cảnh: `mind-bending movie with plot twist`
- truy vấn thiên cảm xúc/khía cạnh: `strong acting and good pacing`

Mục tiêu là xếp hạng danh sách phim theo mức độ liên quan với query và cung cấp tín hiệu giải thích.

## 1.3. Xác định đúng loại task NLP
Đề tài gồm 2 nhóm task chính:
- **Task chính**: Information Retrieval / Ranking trên review text để gợi ý phim.
- **Task bổ trợ**: ABSA (Aspect-Based Sentiment Analysis) để tinh chỉnh/giải thích kết quả theo khía cạnh.

> Lưu ý học thuật: trọng tâm chấm điểm là task NLP retrieval/ranking; phần web chỉ là kênh demo.

## 1.4. Mục tiêu hệ thống
- Xây dựng pipeline từ dữ liệu review -> tiền xử lý -> biểu diễn văn bản -> tính điểm liên quan -> xếp hạng.
- So sánh nhiều hướng mô hình (baseline và nâng cao) để chọn cấu hình tốt nhất.
- Đánh giá định lượng bằng metric phù hợp bài toán ranking.
- Cung cấp diễn giải kết quả bằng score breakdown và tín hiệu ABSA.

## 1.5. Input - Output
### Input
- Query text từ người dùng (tiếng Anh là chính).
- Hồ sơ phim đã được xây dựng từ title + overview + genres + review text.
- (Bổ trợ) hồ sơ ABSA theo phim.

### Output
- Danh sách Top-K phim gợi ý.
- Điểm liên quan tổng và các thành phần điểm (title/genre/semantic/bonus).
- (Tuỳ chọn) giải thích theo khía cạnh ABSA.

## 1.6. Phạm vi giải quyết
### Trong phạm vi
- Content-based recommendation dựa trên review text.
- Multi-field ranking (lexical + semantic + khía cạnh).
- Đánh giá thực nghiệm trên tập dữ liệu đã thu thập.

### Ngoài phạm vi
- Collaborative filtering quy mô lớn theo hành vi đa người dùng.
- Hệ online learning từ log production thời gian thực.
- Tối ưu hệ thống phân tán cho dữ liệu cực lớn.

## 1.7. Đóng góp chính của đề tài
- Chuẩn hóa quy trình notebook-first cho toàn bộ train/eval artifact.
- Kết hợp retrieval và ABSA để vừa tăng chất lượng vừa tăng khả năng giải thích.
- Cung cấp bộ minh chứng thực nghiệm bám sát barem chấm.
