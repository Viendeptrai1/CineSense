# Reproducibility Workflow

This document defines a repeatable local workflow from infrastructure to report evidence.

## 1) Start infrastructure

```bash
docker-compose up -d
```

## 2) Ingest or restore data

Option A (restore snapshots):

```bash
python scripts/restore_data.py
```

Option B (ETL from TMDB):

```bash
python -m etl_pipeline.main --pages 10
```

## 3) Run data-quality audit

```bash
python scripts/audit_core_data.py --output-json training/artifacts/latest/core_audit.json
```

## 4) Build recommendation artifacts

```bash
python scripts/run_recommendation_pipeline.py
```

## 5) Run API + frontend

```bash
uvicorn api.main:app --reload --port 8000
cd frontend && python3 -m http.server 3000
```

## 6) Sync report evidence

Use these outputs in report chapters:

- `training/artifacts/latest/core_audit.json`
- `training/artifacts/*/metadata.json`
- `training/artifacts/*/eval.json`
- screenshots from catalog/detail/recommendation flows

Mapping reference:
- `Report_For_This_Project/planning/implementation-evidence-map.md`
