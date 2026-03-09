# CineSense Training Layer

This package contains offline model training, evaluation, and artifact export.

## Responsibilities

- Read normalized data from PostgreSQL `core_*` tables
- Build movie text profiles
- Train baseline and improved recommendation models
- Evaluate with retrieval metrics
- Export runtime-ready artifacts

## Structure

- `config.py` - shared paths and defaults
- `data/` - loading and profile building
- `baselines/` - TF-IDF and Word2Vec baseline scripts
- `models/` - improved embedding model workflows
- `evaluation/` - metrics and experiment evaluation runner
- `artifacts/` - exported model outputs consumed by API

## Quick Start

```bash
python -m training.baselines.train_tfidf --top-k 20
python -m training.models.train_sentence_transformer --top-k 20
python -m training.evaluation.run_eval --artifact-dir training/artifacts/tfidf_latest
```
