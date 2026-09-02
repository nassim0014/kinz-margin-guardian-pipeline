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

**How to run the workflows locally**

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install pandas numpy pytest pydantic SQLAlchemy httpx

# Tests (17 tests, ~0.2s)
pytest tests/ -v

# Lint (48 errors today — 28 auto-fixable, 8 are unused imports)
ruff check src/ api/ tests/

# Full stack via Docker
docker compose up --build -d
# Airflow: http://localhost:8080 | API: http://localhost:8000/docs | Dashboard: http://localhost:8501

# CI runs: .github/workflows/ci.yml — Python 3.11 + 3.12, pytest + syntax check
# CI install: pandas numpy pytest pydantic SQLAlchemy (lightweight, no Airflow/Streamlit)
```

---

## Now

### 8. 🔴 CI `docker` job fails — private `astk` dep can't install without a secret
Once the workflow parses again (item 1), the second job — `docker` ("Docker
build smoke test") — fails. `api/Dockerfile` runs
`pip install -r requirements-api.txt`, and the astk migration (PRs #15/#16,
merged 2026-09-01) added
`analytics-service-toolkit @ git+https://github.com/nassim0014/analytics-service-toolkit@main`
to that file. That repo is **private**. The CI step runs a plain
`docker build` with no `--secret id=astk_pat`, so the `if [ -s /run/secrets/astk_pat ]`
guard in the Dockerfile is false, pip tries an unauthenticated clone and
gets 404.

This was masked until now because the workflow never parsed. Fixing it is an
**owner decision**: it needs an `ASTK_PAT` repo secret (a GitHub token with
read access to `analytics-service-toolkit`) plus `DOCKER_BUILDKIT=1` and
`--secret id=astk_pat,env=ASTK_PAT` on both `docker build` invocations in
`ci.yml`. Do not add the secret plumbing without the owner provisioning the
secret — a half-wired secret still 404s and looks like a code bug.

Interim option the owner may prefer: drop the `docker` job entirely (the
`docker compose` path is already exercised locally) or mark it
`continue-on-error: true` until the secret exists.

### 1. ~~🔴 CI workflow on `main` is broken — no passing run since 2026-08-21~~ ✅
Fixed in PR #<TBD>. Three faults, not the two originally filed:

1. Codecov step's `if:` used **double-quoted** string literals (invalid GHA
   expression syntax) → whole file failed to parse. Now single-quoted.
2. `pytest` was passed `--cov` flags but `pytest-cov` was missing from the
   CI install line. Added.
3. *(new — surfaced by the astk migration after this item was filed)*
   `tests/test_alert_manager.py` did a hard top-level `from astk.alerts …`,
   and `src/alert_manager.py` imported astk at module scope, so the pure
   helper `format_alert_message` (used by `src/dag_logic.py`) dragged the
   private toolkit in. 6 `test_dag_logic.py::TestBuildAlertData` tests failed
   at collection in the lightweight CI env. Fixed: `alert_manager` degrades
   gracefully when astk is absent (`try/except ModuleNotFoundError`), and the
   alert-delivery tests `pytest.importorskip("astk")` like `test_api.py` does
   for fastapi.

PR #14's single commit was **not** reused — it committed a stray
`coverage.xml` artifact and predated fault 3. `coverage.xml` is now in
`.gitignore`.

Verified: CI-equivalent env (no astk) → 48 passed, 24 skipped; full dev env
(astk installed) → 79 passed, 0 skipped. Touches `.github/workflows/**` so it
cannot auto-merge — left for review.

### 2. ~~API routes at 0% coverage~~ ✅ (already done — backlog was stale)
Closed by PR #2 (`test: cover API routes 0%→60% …`). Verified 2026-09-02:
`api/routes/products.py` 100%, `alerts.py` 100%, `thresholds.py` 100%,
`api/main.py` 100%, `api/models.py` 100%. `tests/test_api.py` has ~24 tests
driving the real FastAPI app against an isolated SQLite DB.

### 3. ~~Ruff has no project config — 48 errors~~ ✅ (already done — backlog was stale)
`[tool.ruff]` with `select = ["E9", "F", "B"]` and the B008/`__init__`/tests
per-file-ignores has been in `pyproject.toml` since PR #2 (`e117725`).
`ruff check src/ api/ tests/` → "All checks passed!" as of 2026-09-02.

### 4. ~~Airflow DAG is 488 lines with zero tests~~ ✅
Extracted pure logic (`get_execution_date`, `validate_price_data`,
`build_margin_records`, `build_alert_data`) from the DAG into
`src/dag_logic.py`. 20 new tests in `tests/test_dag_logic.py`.
The DAG now imports and calls these; only DB I/O + Airflow operator
wiring remains in the DAG file. 54 tests pass (was 34).

### 5. ~~Dashboard is 449 lines with zero tests~~ ✅
Extracted pure computation (`compute_adjusted_values`,
`build_scenario_summary`, `fmt_delta`) from `dashboard/app.py` into
`dashboard/analysis.py`. 17 new tests in `tests/test_dashboard_analysis.py`
cover adjustment math, delta formatting, and the full scenario summary
builder (alert states, margin direction). app.py now calls the extracted
functions via inline imports.

## Next

### 6. ~~No CLAUDE.md or .claude/commands/improve.md~~ ✅
Added `CLAUDE.md` with ground rules (never push to main, squash-merge
only, test commands), architecture overview, known traps
(commit-before-fetch, `::text` casts), and loop-engine integration
notes. The `.claude/commands/improve.md` is deferred — the closed-loop
works fine without it since the loop engine drives the PR cycle.

### 7. Requirements use `>=` throughout — no pins
All four `requirements-*.txt` files use `>=` with no upper bound. This
caused a real break in kinz-competitor-intelligence (streamlit 1.60→1.61
changed `AppTest.from_file` behavior). Consider pinning exact versions
for reproducibility — but this is an owner decision, not a unilateral
change.

---

## Done

- **PR #<TBD>** — Item 1: repaired the CI workflow (parse fault + missing
  `pytest-cov` + the astk-import collection failure the astk migration added
  after the item was filed). `alert_manager` now imports without the private
  toolkit; alert-delivery tests `importorskip("astk")`. `coverage.xml`
  gitignored. Verified no-astk → 48 passed / 24 skipped, with-astk → 79
  passed / 0 skipped. Also verified items 2 and 3 were already done by PR #2
  (stale backlog entries, now marked). Filed item 8 (CI `docker` job still
  red — needs an owner-provisioned `ASTK_PAT` secret).

- **PR #1 (this PR)** — Created `docs/IMPROVEMENTS.md` as the first-cycle
  deliverable, AND fixed the 8 unused-import (F401) errors as a same-PR
  improvement (per the owner's "improve each time" instruction). The
  import fixes are auto-generated by `ruff check --fix` — no manual
  judgment, no behaviour change.

  Findings recorded in the backlog: 17 tests pass, 25% coverage (API at
  0%), 48 ruff errors (8 are real unused-import bugs, now fixed). The
  repo is well-structured (clean separation of `src/` logic from `api/`
  routes) but the API layer has no safety net.

## Dropped

(none yet)
