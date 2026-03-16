# ABSA dataset

- **absa_unlabeled.jsonl**: Export từ DB bằng `python -m training.data.absa_prepare --output training/data/absa/absa_unlabeled.jsonl` (tuỳ chọn `--limit 500`). Mỗi dòng: `{"id", "movie_id", "review_id", "text"}`.
- **Gán nhãn tự động** (pseudo-labels): `python -m training.data.absa_auto_label --input training/data/absa/absa_unlabeled.jsonl --output training/data/absa/labeled_absa_auto.jsonl [--limit 500]`. Script dùng từ khóa để phát hiện aspect và VADER để gán sentiment; nhãn có thể nhiễu nhưng đủ để train mở rộng.
- **Gán nhãn tay**: Lưu thành `labeled_absa.jsonl`. Mỗi dòng thêm trường `labels`: list `{"aspect": "...", "sentiment": "..."}`. Ví dụ:
  ```json
  {"id": "...", "movie_id": "...", "review_id": "...", "text": "The acting was great but the script felt weak.", "labels": [{"aspect": "acting", "sentiment": "positive"}, {"aspect": "script", "sentiment": "negative"}]}
  ```
- **Train**: `python -m training.models.absa_model --labeled training/data/absa/labeled_absa_auto.jsonl` (hoặc `labeled_absa.jsonl` / `labeled_absa_demo.jsonl`). Nên có 300–500+ dòng đã gán nhãn.
