# Rubric Checklist For Maximum Score

## 1. Mức độ hoàn thiện đề tài (1.5)
- [ ] Xác định rõ bài toán NLP thuộc loại Similarity/Retrieval.
- [ ] Có bảng Input / Output / Task minh họa.
- [ ] Trình bày mục tiêu, phạm vi và ranh giới bài toán.
- [ ] Mô tả nguồn dữ liệu, ngôn ngữ, số lượng mẫu và train/val/test split.

## 2. Cơ sở lý thuyết (1.0)
- [ ] Trình bày tokenization, embedding, language model.
- [ ] Giải thích đúng TF-IDF, Word2Vec/FastText, Sentence Transformer.
- [ ] Liên hệ trực tiếp lý thuyết với bài toán recommendation của CineSense.

## 3. Tiền xử lý dữ liệu (1.5)
- [ ] Có pipeline làm sạch dữ liệu.
- [ ] Giải thích vì sao chọn từng bước tiền xử lý.
- [ ] Có trực quan hóa dữ liệu: độ dài text, phân bố review, word frequency.
- [ ] Có ví dụ data trước và sau xử lý.

## 4. Xây dựng mô hình (2.5)
- [ ] Có ít nhất 1 baseline.
- [ ] Có ít nhất 1 mô hình cải tiến.
- [ ] Có mô tả rõ input-output.
- [ ] Có sơ đồ pipeline text -> preprocessing -> vectorization -> model -> output.
- [ ] Có siêu tham số, train/val/test và tránh data leakage.
- [ ] Có biểu đồ training/loss nếu có fine-tuning.

## 5. Đánh giá và thực nghiệm (1.5)
- [ ] Có metric đúng task: Cosine similarity và Precision@k.
- [ ] Có bảng so sánh mô hình.
- [ ] Có minh họa trực quan.
- [ ] Có phân tích lỗi, hạn chế và hướng cải thiện.

## 6. Demo ứng dụng (1.0)
- [ ] Website chạy được.
- [ ] Có screenshot từng bước.
- [ ] Có kịch bản demo.
- [ ] Có video demo dự phòng.

## 7. Báo cáo và bảo vệ (1.0)
- [ ] Báo cáo tối thiểu 40 trang không tính phụ lục.
- [ ] Có đủ 7 chương bắt buộc.
- [ ] Có hình minh họa và pseudo-code.
- [ ] Tài liệu tham khảo đúng chuẩn IEEE.
- [ ] Chuẩn bị câu hỏi phản biện về dữ liệu, mô hình, metric, giới hạn.
