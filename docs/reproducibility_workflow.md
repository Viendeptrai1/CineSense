# Reproducibility Workflow

This document defines a repeatable local workflow from data to report evidence.

## 1) Create SQLite database from CSV + artifacts

```bash
python scripts/seed_sqlite_from_csv.py
```

## 2) Optional: ETL from TMDB (requires `TMDB_API_KEY` in `.env`)

```bash
python -m etl_pipeline.main --pages 10
```

## 3) Run data-quality audit

```bash
python scripts/audit_core_data.py --output-json Notebook_Report/training/artifacts/latest/core_audit.json
```

## 4) Build recommendation artifacts

Use notebook-first workflow:

- `Notebook_Report/03_Modeling_Baselines.ipynb`
- `python -m Notebook_Report.retrieval.build_query_bank`
- `python -m Notebook_Report.retrieval.finetune_biencoder`
- `Notebook_Report/04_Advanced_ABSA_Modeling.ipynb`
- `python -m Notebook_Report.retrieval.eval_llm_judge --dry-run`
- `Notebook_Report/05_Model_Evaluation.ipynb`

## 5) Run API + frontend

```bash
uvicorn api.main:app --reload --port 8000
cd frontend && python3 -m http.server 3000
```

## 6) Sync report evidence

Use these outputs in report chapters:

- `Notebook_Report/training/artifacts/latest/core_audit.json`
- `Notebook_Report/training/artifacts/*/metadata.json`
- `Notebook_Report/training/artifacts/*/eval.json`
- `Notebook_Report/training/datasets/retrieval_query_bank_v1/*`
- `Notebook_Report/llm_judge_runs/*/summary.json`
- screenshots from catalog/detail/recommendation flows

Mapping reference:
- `Notebook_Report/README.md`
