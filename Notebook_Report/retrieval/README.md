# Retrieval English-First Companion Scripts

Các script trong thư mục này bổ sung cho notebook 03 và 05:

- `build_query_bank.py`
  - Sinh query bank đa dạng theo 3 strata: `keyword`, `vibe`, `detailed`
  - Export pairs/triplets cho fine-tune và judge
- `finetune_biencoder.py`
  - Fine-tune English bi-encoder trên query bank nội bộ
  - Export artifact `sbert_en_finetuned_latest/` để runtime dùng trực tiếp
- `eval_llm_judge.py`
  - Chạy Gemini 2.5 Flash offline như LLM-as-a-Judge
  - Sinh `retrieval_traces.jsonl`, `judge_scores.jsonl`, `judge_errors.jsonl`, `summary.json`, `human_audit_sample.csv`
  - Có retry/backoff cho `429` / `5xx`, ghi partial results thay vì làm hỏng toàn bộ batch

Ví dụ chạy:

```bash
source .venv/bin/activate
python -m Notebook_Report.retrieval.build_query_bank
python -m Notebook_Report.retrieval.finetune_biencoder
python -m Notebook_Report.retrieval.eval_llm_judge --dry-run
python -m Notebook_Report.retrieval.eval_llm_judge --models tfidf_latest sbert_en_finetuned_latest --max-queries 12 --top-k 2 --sleep-s 2
```

Lưu ý:

- Không hard-code `GEMINI_API_KEY`; chỉ dùng biến môi trường.
- Judge script gửi API key qua request header, không nhét key vào URL.
- Nếu gặp quota/rate limit, xem `judge_errors.jsonl` và `summary.json` để biết batch hoàn thành toàn phần hay một phần.
- Output dữ liệu sinh thêm nằm trong `Notebook_Report/training/datasets/` và `Notebook_Report/llm_judge_runs/`.
