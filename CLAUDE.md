# kinz-margin-guardian-pipeline — Agent Guidance

## What this is

Airflow pipeline + FastAPI + Streamlit dashboard for tracking KINZ's
COGS (cost of goods sold) and margins. Private repo under `nassim0014`.

## Rules (inherited from the loop engine)

1. **Never push directly to `main`** — open a PR, squash-merge.
2. **Squash-merge only** — so a revert is one command.
3. **Never create GitHub issues** — owner wants 0%.
4. **Never change repository visibility.**
5. **Never rewrite git history or force-push.**
6. **Never delete a branch other than one created this run.**
7. **Never run the genesis loop** before ~2026-08-30 (owner pause).

## Architecture

```
airflow/          Airflow DAGs (the main pipeline)
  dags/
    margin_tracking_dag.py   ~488 lines — the main DAG
api/              FastAPI app (margin/alert routes)
  routes/
dashboard/        Streamlit dashboard (~449 lines)
src/              Shared library code
tests/            pytest suite (79 tests)
docs/             IMPROVEMENTS.md backlog
```

## Development workflow

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy pytest pydantic SQLAlchemy httpx

# Tests (79 tests, ~3s)
pytest tests/ -v

# Lint
ruff check src/ api/ tests/

# Full stack via Docker
docker compose up --build -d    # Airflow :8080, API :8000, Dashboard :8501
```

### CI dependencies

The 22 API tests need `fastapi httpx PyJWT slowapi` installed in CI
(they skip gracefully via `pytest.importorskip` if not present). See
§7.4 of the handoff — the CI install step should include these.

## Known traps

- **Airflow DAG has zero tests** (item 3 in backlog — 488 lines). The
  DAG logic should be extracted to `src/` so it can be tested without
  a running Airflow instance.
- **Dashboard has zero tests** (item 4 — 449 lines). Same pattern:
  extract logic to `src/` and test it there.
- **`commit-before-fetch` bug on RETURNING**: PostgreSQL tolerates
  committing before fetching the RETURNING clause, SQLite doesn't.
  Always fetch first, then commit. Fixed in PR #2 but documented here
  so it doesn't regress.
- **`::text` → `CAST(... AS TEXT)`**: the original code used
  PostgreSQL-specific `::text` casts. These were changed to
  `CAST(... AS TEXT)` for portability (SQLite compatibility in tests).
  Don't reintroduce `::text`.

## Loop-engine integration

This repo is in the closed-loop rotation (position 3 in the cursor).
The loop engine works it every 2 days, opening small PR-based
improvements. See `docs/IMPROVEMENTS.md` for the current backlog.
