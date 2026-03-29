# Chương 5. Đánh giá mô hình và thực nghiệm

## 5.1. Thiết kế đánh giá
Mục tiêu đánh giá:
- Đo chất lượng retrieval/ranking cho bài toán gợi ý phim.
- Đo chất lượng ABSA ở mức nhãn khía cạnh-cảm xúc.
- So sánh công bằng giữa các cấu hình mô hình.
- Bổ sung chấm điểm **LLM-as-a-Judge** và kiểm chứng tay trên mẫu nhỏ theo góp ý của giảng viên.

## 5.2. Bộ metric
## 5.2.1. Retrieval/Ranking
- Precision@k
- Recall@k
- NDCG@k
- (mở rộng) MRR@k nếu có
- LLM relevance score / binary relevant rate theo rubric
- Agreement giữa human audit và LLM judge (nếu mẫu tay đã điền xong)

## 5.2.2. ABSA
- Micro-F1
- Macro-F1
- (tùy chọn) hỗ trợ thêm confusion matrix theo sentiment/aspect tổng hợp

## 5.3. Kịch bản thực nghiệm
- Query ngắn theo từ khóa.
- Query mô tả ngữ cảnh dài.
- Query thiên cảm xúc/khía cạnh.

Mỗi truy vấn được đưa vào query bank versioned để đảm bảo:
- cùng tập query cho mọi mô hình;
- có thể tách riêng train/dev/judge;
- có log nguồn phim, stratum, positive candidates và hard negative.

Mỗi kịch bản đo trên nhiều cấu hình:
- lexical baseline
- semantic baseline
- artifact recommender
- artifact + ABSA refine
- (nếu có) artifact + personalization/rerank.

Với phần LLM judge:
- sử dụng Gemini 2.5 Flash ở chế độ **offline batch**;
- prompt có rubric rõ ràng, yêu cầu trả score **và reasoning**;
- movie evidence đưa vào gồm `overview` + `review_summary`, tránh chấm chỉ dựa trên title.

## 5.4. Bảng kết quả chính (khung trình bày)
| Cấu hình | Precision@10 | Recall@10 | NDCG@10 | Ghi chú |
| --- | --- | --- | --- | --- |
| Baseline lexical | ... | ... | ... | ... |
| Semantic | ... | ... | ... | ... |
| Artifact recommender | ... | ... | ... | ... |
| Artifact + ABSA | ... | ... | ... | ... |
| Artifact + ABSA + Personalization | ... | ... | ... | ... |

## 5.5. Minh họa trực quan
- Biểu đồ cột so sánh metric theo cấu hình.
- Đồ thị/heatmap sai số.
- Ví dụ truy vấn thực tế kèm top kết quả dự đoán.
- Bảng điểm LLM judge theo từng stratum (`keyword`, `vibe`, `detailed`).
- File `human_audit_sample.csv` cho 50-100 mẫu để đối chiếu thủ công.

## 5.6. Thảo luận kết quả
Các ý bắt buộc:
- Mô hình nào tốt nhất và vì sao.
- Khi nào lexical thắng semantic, khi nào ngược lại.
- ABSA cải thiện ở nhóm query nào.
- Tác động của personalization/re-rank đến chất lượng và độ trễ.
- LLM judge có đồng thuận với người chấm tay hay không; nếu lệch, lệch ở kiểu query nào.

## 5.7. Hạn chế
- Dữ liệu nhãn yếu (weak supervision/pseudo-label) có thể gây nhiễu.
- Chưa có lượng lớn tương tác người dùng thật để huấn luyện ranking phức tạp.
- Một số query mơ hồ khó phân định ý định.
- LLM judge vẫn là proxy evaluator; cần ghi rõ prompt version, model version, và manual audit để tránh phụ thuộc mù quáng vào LLM.

## 5.8. Kết luận chương
Chương đánh giá cần chứng minh đủ 3 tiêu chí barem:
- metric định lượng phù hợp,
- minh họa trực quan rõ,
- thảo luận có chiều sâu và nêu hướng cải thiện.
