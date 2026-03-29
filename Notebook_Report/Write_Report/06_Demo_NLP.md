# Chương 6. Demo hệ thống (trọng tâm NLP)

## 6.1. Mục tiêu demo
- Chứng minh pipeline NLP hoạt động end-to-end:
  - query text -> truy hồi/xếp hạng -> giải thích kết quả.
- Không sa đà vào chi tiết UI; UI chỉ là phương tiện trình diễn.

## 6.2. Kịch bản demo đề xuất
## 6.2.1. Kịch bản A: Query ngắn theo keyword
- Ví dụ: `crime thriller`
- Kỳ vọng: artifact recommender phản hồi nhanh, kết quả đúng chủ đề.

## 6.2.2. Kịch bản B: Query ngữ cảnh dài
- Ví dụ: `mind-bending movie with plot twist and smart detective`
- Kỳ vọng: tín hiệu semantic của artifact và re-rank phát huy tốt hơn keyword thuần.

## 6.2.3. Kịch bản C: Query theo cảm xúc/khía cạnh
- Ví dụ: `strong acting and good pacing`
- Kỳ vọng: ABSA refine kích hoạt bonus ở phim có profile khía cạnh phù hợp.

## 6.3. Nội dung cần trình bày khi demo
- Query đầu vào.
- Top kết quả trả về và lý do xếp hạng.
- Score breakdown (title/genre/semantic/ABSA/user match nếu có).
- So sánh nhanh bật/tắt ABSA refine hoặc rerank để thấy tác động.

## 6.4. Tiêu chí chấm demo theo barem
- Demo chạy được.
- Input/Output rõ ràng.
- Có kịch bản sử dụng cụ thể, phản ánh tính hữu ích thực tế.

## 6.5. Gợi ý script thuyết trình demo (1-2 phút)
1. Nêu query và ý định truy vấn.
2. Cho thấy top-k và điểm thành phần.
3. Giải thích vì sao kết quả đứng đầu.
4. Bật/tắt một cơ chế (ABSA/rerank) để chứng minh đóng góp NLP.
