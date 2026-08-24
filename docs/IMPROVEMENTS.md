# Improvement backlog

The queue the closed-loop improvement cycle works from. One item per run,
highest value first. Items are added whenever something is noticed but is
too far out of scope to fix on the spot.

**Rules**

- Work the top unblocked item. Don't cherry-pick easy ones.
- One PR per item. If an item turns out to be three things, split it and
  re-rank.
- Move finished items to *Done* with the PR number. Don't delete them —
  the history is how the next session learns what has already been tried.
- If an item turns out to be wrong or no longer applies, move it to
  *Dropped* with the reason. That is a legitimate outcome.
- **Tick items off promptly.** Items 1 and 2 below sat marked "Now" for
  five cycles after PR #2 had already resolved both — a future session
  nearly redid the work before noticing `pyproject.toml` already had the
  ruff config and `pytest --cov` already showed 100% on the routes in
  question. Verify a symptom is still present in the code before trusting
  this file's headings.

**How to run the workflows locally**

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy pytest pytest-cov pydantic SQLAlchemy httpx fastapi PyJWT slowapi ruff

# Tests (79 tests, ~3s)
pytest tests/ -v --cov=api --cov=src --cov-report=term-missing

# Lint (0 errors — select = ["E9", "F", "B"] in pyproject.toml)
ruff check src/ api/ tests/ dashboard/ scripts/

# Full stack via Docker
docker compose up --build -d
# Airflow: http://localhost:8080 | API: http://localhost:8000/docs | Dashboard: http://localhost:8501

# CI runs: .github/workflows/ci.yml — Python 3.11 + 3.12, pytest + syntax check
# CI install: pandas numpy pytest pydantic SQLAlchemy fastapi httpx PyJWT slowapi (see PR #6)
```

---

## Now

### 6. Requirements use `>=` throughout — no pins
All four `requirements-*.txt` files use `>=` with no upper bound. This
caused a real break in kinz-competitor-intelligence (streamlit 1.60→1.61
changed `AppTest.from_file` behavior). Consider pinning exact versions
for reproducibility — but this is an owner decision, not a unilateral
change.

### 7. Small remaining coverage gap in `api/database.py::get_db` (4 lines, 69%)
`get_db()`'s try/yield/finally is only exercised via FastAPI's
`dependency_overrides` in tests (see `conftest.py::client`), which bypasses
the real generator body. A direct unit test (call `next(get_db())`, assert
a `Session` comes back, call `.close()`) would close this, but the value is
low — five lines of stdlib dependency-injection plumbing, not application
logic worth chasing for the coverage number alone. Noted rather than picked
up this cycle; pick up only if the backlog otherwise runs dry.

---

## Done

- **PR #12** — Added a bug-report issue template.
- **PR #11** — Added `.pre-commit-config.yaml` for ruff.
- **PR #10** — Added `SECURITY.md` with a reporting policy.
- **PR #9** — Added `CONTRIBUTING.md` with dev setup + PR workflow.
- **PR #8** — Added coverage reporting + Codecov upload to CI.
- **PR #7** — Added ruff to CI, checked Makefile targets, fixed a
  `conftest.py` `sys.path` issue blocking the dashboard import.
- **PR #6** — Installed `fastapi httpx PyJWT slowapi` in CI so the 22 API
  tests actually run there instead of skipping via `importorskip`.
- **PR #5 (item 3)** — ~~Airflow DAG is 488 lines with zero tests~~ ✅
  Extracted pure logic (`get_execution_date`, `validate_price_data`,
  `build_margin_records`, `build_alert_data`) from the DAG into
  `src/dag_logic.py`. 20 new tests in `tests/test_dag_logic.py`. The DAG
  now imports and calls these; only DB I/O + Airflow operator wiring
  remains in the DAG file.
- **PR #4 (item 4)** — ~~Dashboard is 449 lines with zero tests~~ ✅
  Extracted pure computation (`compute_adjusted_values`,
  `build_scenario_summary`, `fmt_delta`) from `dashboard/app.py` into
  `dashboard/analysis.py`. 17 new tests in `tests/test_dashboard_analysis.py`.
- **PR #3 (item 5)** — ~~No CLAUDE.md or .claude/commands/improve.md~~ ✅
  Added `CLAUDE.md` with ground rules, architecture overview, known traps
  (commit-before-fetch, `::text` casts), and loop-engine integration notes.
  `.claude/commands/improve.md` deferred — the closed-loop drives the PR
  cycle fine without it.
- **PR #2 (items 1 and 2)** — ~~API routes at 0% coverage~~ ✅ and
  ~~ruff has no project config~~ ✅. Both were done in the same PR and
  neither got ticked off here at the time — see the note at the top of
  this file. Coverage went from 25% (API at 0%) to 60%+ on the API layer
  via `TestClient` against the real FastAPI app with an isolated SQLite
  test DB; `[tool.ruff.lint] select = ["E9", "F", "B"]` was added to
  `pyproject.toml`, silencing 40 style-opinion errors while keeping the 8
  real F401 bugs (already fixed in PR #1) enforced. Also fixed a
  `commit-before-fetch` bug: PostgreSQL tolerates committing before
  fetching a `RETURNING` clause, SQLite doesn't — documented in
  `CLAUDE.md` so it doesn't regress.
- **PR #1** — Created `docs/IMPROVEMENTS.md` as the first-cycle
  deliverable, AND fixed the 8 unused-import (F401) errors as a same-PR
  improvement (per the owner's "improve each time" instruction).
- **This PR** — Backlog bookkeeping correction (items 1 and 2 above were
  already resolved in PR #2 but never ticked off — moved to *Done* with
  the real history; PRs #3–#12, which also happened but were never
  recorded here, added retroactively). Same-PR code contribution: closed
  the remaining real coverage gaps in `api/auth.py` (`verify_token`'s
  expired/invalid-JWT branches, 86%→100%) and `src/alert_manager.py`
  (Slack non-200-response branch, 93%→100%) — overall coverage 97%→99%
  (330 stmts, 4 missed, all in the low-value `get_db` generator, item 7
  above). Verified each new test actually catches a regression by
  temporarily breaking the corresponding code path and confirming the
  test failed, then restoring it (see PR description). No production
  logic changed — test-only PR. Also surfaced a real, previously-untested
  behavioral detail while writing these: `send_slack_alert` returns
  `False` on a non-200 HTTP response but `True` on a raised exception
  (network error) — the two failure modes are handled asymmetrically on
  purpose (a raised exception still falls back to logging so the alert
  isn't silently lost; a clean non-200 response is treated as a real
  failure). Documented via the new test's docstring rather than changed,
  since changing behavior here is an owner call, not something this PR
  scope covers.

## Dropped

(none yet)
