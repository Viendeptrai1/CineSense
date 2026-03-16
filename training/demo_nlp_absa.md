# Demo: NLP pipeline & ABSA (CineSense)

Dùng cho báo cáo / slide: minh hoạ pipeline làm sạch text, similarity và Aspect-Based Sentiment Analysis.

## 1. Text cleaning (trước / sau)

```python
from etl_pipeline.embedder import preprocess_text, is_noisy_review

raw = "<p>Great movie!!!  https://spam.com  The acting was 🔥🔥</p>"
cleaned = preprocess_text(raw)
# → "great movie!!! the acting was"
# HTML bỏ, URL bỏ, emoji bỏ, lowercase, whitespace chuẩn hoá.

is_noisy_review("... ... ... ...")  # True
is_noisy_review("The script was weak but visuals were stunning.")  # False
```

## 2. Cosine similarity (embedding English)

```python
from etl_pipeline.embedder import embed_text, cosine_similarity

a = embed_text("Dark thriller with great twists")
b = embed_text("Psychological horror, surprising plot")
cosine_similarity(a, b)  # ~0.7+
```

## 3. ABSA (aspect–sentiment)

Sau khi train: `python -m training.models.absa_model --labeled training/data/absa/labeled_absa_demo.jsonl`

```python
from pathlib import Path
import torch
from training.models.absa_model import load_absa_artifact, predict_aspects

model, tokenizer, schema = load_absa_artifact(Path("training/artifacts/absa_latest"))
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
results = predict_aspects(model, tokenizer, ["The script was weak but the acting was brilliant."], device)
# → [[{"aspect": "script", "sentiment": "negative", "score": 0.8}, {"aspect": "acting", "sentiment": "positive", "score": 0.9}]]
```

## 4. API test

```bash
# Backend: uvicorn api.main:app --port 8000
python scripts/test_api.py --base-url http://localhost:8000
# POST /absa/analyze với body {"text": "..."} để xem aspect–sentiment.
```
