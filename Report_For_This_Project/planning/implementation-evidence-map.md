# Implementation To Report Evidence Map

This file links concrete implementation artifacts to report chapters.

## Chapter 3 (Dataset / Preprocessing)

- `scripts/audit_core_data.py`
- `training/artifacts/latest/core_audit.json`
- `docs/data_contract.md`

## Chapter 4 (Methodology)

- `training/data/loaders.py`
- `training/data/profiles.py`
- `training/data/splits.py`
- `training/baselines/train_tfidf.py`
- `training/models/train_sentence_transformer.py`

## Chapter 5 (Experiments / Results)

- `training/evaluation/metrics.py`
- `training/evaluation/run_eval.py`
- `training/artifacts/*/eval.json`
- `training/artifacts/*/metadata.json`

## Chapter 6 (Demo Application)

- `api/routes/recommendations.py`
- `api/recommender.py`
- `frontend/app.js`
- `frontend/index.html`
- `frontend/movie.html`

## Chapter 7 (Conclusion / Future Work)

- `README.md` roadmap and reproducibility commands
- `scripts/run_recommendation_pipeline.py`
