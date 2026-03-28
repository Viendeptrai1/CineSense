# Chương 5. Đánh giá mô hình và thực nghiệm

## 5.1. Thiết kế đánh giá
Mục tiêu đánh giá:
- Đo chất lượng retrieval/ranking cho bài toán gợi ý phim.
- Đo chất lượng ABSA ở mức nhãn khía cạnh-cảm xúc.
- So sánh công bằng giữa các cấu hình mô hình.

## 5.2. Bộ metric
## 5.2.1. Retrieval/Ranking
- Precision@k
- Recall@k
- NDCG@k
- (mở rộng) MRR@k nếu có

## 5.2.2. ABSA
- Micro-F1
- Macro-F1
- (tùy chọn) hỗ trợ thêm confusion matrix theo sentiment/aspect tổng hợp

## 5.3. Kịch bản thực nghiệm
- Query ngắn theo từ khóa.
- Query mô tả ngữ cảnh dài.
- Query thiên cảm xúc/khía cạnh.

Mỗi kịch bản đo trên nhiều cấu hình:
- lexical baseline
- semantic baseline
- hybrid
- hybrid + ABSA refine
- (nếu có) hybrid + personalization/rerank.

## 5.4. Bảng kết quả chính (khung trình bày)
| Cấu hình | Precision@10 | Recall@10 | NDCG@10 | Ghi chú |
| --- | --- | --- | --- | --- |
| Baseline lexical | ... | ... | ... | ... |
| Semantic | ... | ... | ... | ... |
| Hybrid | ... | ... | ... | ... |
| Hybrid + ABSA | ... | ... | ... | ... |
| Hybrid + ABSA + Personalization | ... | ... | ... | ... |

## 5.5. Minh họa trực quan
- Biểu đồ cột so sánh metric theo cấu hình.
- Đồ thị/heatmap sai số.
- Ví dụ truy vấn thực tế kèm top kết quả dự đoán.

## 5.6. Thảo luận kết quả
Các ý bắt buộc:
- Mô hình nào tốt nhất và vì sao.
- Khi nào lexical thắng semantic, khi nào ngược lại.
- ABSA cải thiện ở nhóm query nào.
- Tác động của personalization/re-rank đến chất lượng và độ trễ.

## 5.7. Hạn chế
- Dữ liệu nhãn yếu (weak supervision/pseudo-label) có thể gây nhiễu.
- Chưa có lượng lớn tương tác người dùng thật để huấn luyện ranking phức tạp.
- Một số query mơ hồ khó phân định ý định.

## 5.8. Kết luận chương
Chương đánh giá cần chứng minh đủ 3 tiêu chí barem:
- metric định lượng phù hợp,
- minh họa trực quan rõ,
- thảo luận có chiều sâu và nêu hướng cải thiện.
