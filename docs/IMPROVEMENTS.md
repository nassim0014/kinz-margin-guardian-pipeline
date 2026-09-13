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

### 8. 🔴 CI `docker` job's "pass" is a side effect of an unexplained repo-visibility change — not a real fix
`api/Dockerfile` runs `pip install -r requirements-api.txt`, which does an
unauthenticated `git+https` clone of `analytics-service-toolkit` unless the
BuildKit `astk_pat` secret is mounted (see the Dockerfile comment). No such
secret is configured on this repo. This job was red for exactly that reason
until ~2026-09-12.

**As of the 2026-09-13 closed-loop cycle it is green again — but not because
anyone provisioned the secret.** `analytics-service-toolkit` itself was found
**unexpectedly public** on GitHub (recorded private as of 2026-09-10; flagged
loop-wide, not repo-specific — see that cycle's report,
`NEEDS YOUR DECISION`). An unauthenticated clone of a public repo just works,
which is the entire reason `docker build` stopped failing — `git ls-remote
https://github.com/nassim0014/analytics-service-toolkit.git` succeeds with no
credentials at all right now. **If that visibility is reverted (which it
should be, since no loop or agent made the change deliberately), this job
goes red again immediately**, exactly as originally filed below.

Original filing, still the actual owner decision needed regardless of the
visibility question: it needs an `ASTK_PAT` repo secret (a GitHub token with
read access to `analytics-service-toolkit`) plus `DOCKER_BUILDKIT=1` and
`--secret id=astk_pat,env=ASTK_PAT` on both `docker build` invocations in
`ci.yml`. Do not add the secret plumbing without the owner provisioning the
secret — a half-wired secret still 404s and looks like a code bug. Interim
option the owner may prefer: drop the `docker` job entirely (the `docker
compose` path is already exercised locally) or mark it
`continue-on-error: true` until the secret exists.

### 9. ~~CI still red on `main` — item 1's astk fix missed `src/config.py`~~ ✅
Found by the repo-review-loop, 2026-09-13, checking `main` CI directly.
Confirmed and fixed by the closed-loop the same day. `src/config.py` had the
identical unconditional-import problem as item 1's `alert_manager.py` fault,
just not caught at the time because item 1 was scoped to the failures visible
at that moment: `from astk.settings import BaseServiceSettings, load_settings`
at module scope, with `GuardianSettings(BaseServiceSettings)` and
`settings = load_settings(GuardianSettings)` evaluated eagerly. `src/margin_engine.py`,
`src/dag_logic.py` and `dashboard/analysis.py` all import from `src.config` at
module scope, so all three of `tests/test_dag_logic.py`,
`tests/test_dashboard_analysis.py` and `tests/test_margin_engine.py` failed at
**collection** (not just at test-run) with `ModuleNotFoundError: No module
named 'astk'` in the lightweight CI env — which aborts the entire pytest
session (`Interrupted: 3 errors during collection`, exit code 2), so none of
the 39+ tests in the suite ran at all, not just the three affected files.

Unlike `alert_manager.py` (whose astk-dependent code is only reached lazily,
inside function bodies), `config.py`'s constants are consumed eagerly at
import time by three different modules, so a bare `try/except` around the
import alone isn't enough — the fallback branch has to actually populate
every constant. Restored the exact bare `os.getenv` calls (same env var
names, same defaults) this module used before the astk migration
(`git show 5368ef5:src/config.py`) as the `except ModuleNotFoundError` branch.
Every constant resolves to the same value whether or not astk is installed;
only the pydantic validation layer is skipped when it isn't.

Verified: CI-equivalent env (`.venv`, no astk) → 48 passed, 24 skipped —
back to item 1's baseline. Full dev env (astk installed, via a venv with
`analytics-service-toolkit` installed editable) → 79 passed, 0 skipped —
unchanged from item 1. Proved the regression: reverted to the unconditional
import (`git stash`), confirmed the same 3-collection-error/exit-code-2
failure reproduces exactly, restored (`git stash pop`).

**Noticed but not fixed here** (scope discipline — added below as item 11):
even with this fix, the 23 `tests/test_api.py` tests and 1
`test_alert_manager.py` test still *skip* in the lightweight CI env — via
`tests/conftest.py`'s `client` fixture, which catches `ImportError` from
`api.database` (which hard-imports `astk.db.make_engine`) and skips with the
message "fastapi not installed", even though fastapi *is* installed and the
real cause is the same missing-astk situation this item just fixed for
`config.py`. The tests still don't run in CI; they just don't abort the
whole session anymore, and the reason they're skipped is currently reported
wrong.

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

### 11. API tests silently skip in CI with a wrong reason
`tests/conftest.py`'s `client` fixture wraps `from api.database import
get_db` / `from api.main import app` in `try/except ImportError:
pytest.skip("fastapi not installed — skipping API tests")`. In the
lightweight CI env fastapi **is** installed (CI installs it explicitly —
see item 2), but `api/database.py` hard-imports `astk.db.make_engine` at
module scope with no fallback, so the import still raises (a
`ModuleNotFoundError`, which is an `ImportError` subclass) and the fixture
catches it — skipping all 23 `test_api.py` tests and reporting the wrong
cause. Net effect: the API route tests item 2 added have not actually run
in CI since the astk migration (PRs #15/#16), only silently skipped, and
the skip message actively points at the wrong dependency.

Same shape as item 9's `config.py` fix, but for `api/database.py`: either
give it the same `try/except ModuleNotFoundError` fallback (needs a
non-astk `make_engine` equivalent — the module docstring lists exactly what
astk's version buys: cached-per-URL, `pool_pre_ping=True`,
SQLite-in-memory-safe), or at minimum split the `client` fixture's catch so
a missing-astk `ImportError` reports the real cause instead of "fastapi not
installed". Left unranked-highest deliberately: item 9 already restored CI
to a *passing* (not deceptive) state; this is a message-accuracy /
test-execution-completeness issue on top of that, not a currently-red build.

---

## Done

- **PR #23 (this PR)** — Item 9: `src/config.py` had the same unconditional
  `from astk.settings import …` fault item 1 fixed in `alert_manager.py`,
  just not caught at the time. Fixed with the same `try/except
  ModuleNotFoundError` pattern, except the fallback branch has to actually
  populate every constant (config.py's are consumed eagerly at import time,
  unlike alert_manager's lazily-used helpers) — restored the exact bare
  `os.getenv` calls this module used pre-migration. Verified: no-astk → 48
  passed / 24 skipped (item 1's baseline, restored); with-astk → 79 passed /
  0 skipped (unchanged). Proved the regression by reverting to the
  unconditional import and confirming the identical 3-collection-error
  abort, then restoring. Also corrected item 8's record (the `docker` job's
  current green state is a side effect of `analytics-service-toolkit`'s
  unexplained public visibility, not a real fix — see that item) and filed
  item 11 (API tests skip in CI with a misleading reason).

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
