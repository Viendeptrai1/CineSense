# CineSense Data Contract (English-First Core)

This document defines the stable AI-facing contract for model training and runtime recommendation.

## Source Of Truth

- `core_movies`
- `core_reviews`
- `core_genres`
- `core_movie_genres`

Defined in:
- `etl_pipeline/database.py`

## Required Fields

### core_movies

- `id`
- `tmdb_id`
- `title`
- `overview`

Recommended for ranking features:
- `popularity`
- `vote_average`
- `vote_count`
- `release_date`
- `poster_path`

### core_reviews

- `id`
- `movie_id`
- `content`
- `source`
- `language`

Recommended provenance fields:
- `external_review_id`
- `source_created_at`
- `source_url`

## Language Policy

- Runtime and training default to English-first corpus.
- ETL sets `language` via a lightweight heuristic when ingesting review text.
- Unknown/noisy reviews should be marked `unknown` and excluded from strict English training runs.

## Canonical Embedding Spec

- English bi-encoder fine-tuned from `sentence-transformers/all-MiniLM-L6-v2`
- embedding dimension: `384`
- distance metric: `cosine`

The runtime contract now depends on artifact metadata, not just a raw HF model id. A serving-ready retrieval artifact should expose:
- `artifact_type`
- `artifact_version`
- `model_name`
- `base_model_name`
- `document_text_field`
- `text_representation`
- `fine_tuned`

`movie_index.json` rows should keep the lightweight movie metadata plus a `search_text` field when the semantic retriever was trained on review-driven text.

This spec must remain consistent across:
- `.env`
- `api/recommender.py`
- `Notebook_Report/retrieval/finetune_biencoder.py`
- exported `metadata.json`

## Reproducible Audit

Run:

```bash
python scripts/audit_core_data.py --output-json Notebook_Report/training/artifacts/latest/core_audit.json
```

Use the output as:
- experiment preflight check
- report evidence input for dataset quality tables
