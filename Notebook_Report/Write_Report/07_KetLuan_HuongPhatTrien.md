# Chương 7. Kết luận và hướng phát triển

## 7.1. Kết luận chính
Đề tài đã xây dựng được quy trình NLP cho bài toán **Gợi Ý Phim Dựa Trên Review Text** với các thành phần cốt lõi:
- tiền xử lý dữ liệu văn bản,
- mô hình retrieval/ranking đa tín hiệu,
- thành phần ABSA để bổ trợ tinh chỉnh và giải thích,
- hệ đánh giá định lượng theo metric phù hợp.

## 7.2. Đóng góp học thuật
- Xác định rõ bài toán NLP và task chính/phụ.
- Thiết lập pipeline nhất quán từ data -> model -> evaluation.
- Minh chứng thực nghiệm có so sánh và phân tích lỗi.

## 7.3. Hạn chế hiện tại
- Chất lượng nhãn ABSA phụ thuộc mức độ chính xác của pseudo-label hoặc dữ liệu nhãn hạn chế.
- Chưa khai thác đầy đủ hành vi người dùng thật ở quy mô lớn.
- Một số truy vấn mơ hồ cần mô hình hiểu ngữ cảnh sâu hơn.

## 7.4. Hướng phát triển
- Nâng cấp retrieval bằng chỉ mục và reranking mạnh hơn.
- Tăng chất lượng nhãn ABSA bằng quy trình gán nhãn bán tự động + kiểm duyệt tay.
- Tối ưu personalization bằng dữ liệu lịch sử truy vấn/click dài hạn.
- Chuẩn hóa bộ benchmark và ablation để theo dõi tiến bộ qua từng phiên bản.

## 7.5. Giá trị thực tiễn
Giải pháp có thể áp dụng cho hệ thống khám phá nội dung giải trí dựa trên văn bản phản hồi người dùng, đồng thời cung cấp cơ chế giải thích giúp tăng độ tin cậy khi sử dụng mô hình gợi ý.
