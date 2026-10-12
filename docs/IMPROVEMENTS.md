# Improvements backlog

A fresh list, built 2026-10-12 by actually reading `src/`, `api/`, `tests/` and
`scripts/demo.py` on current `main`. The previous `docs/IMPROVEMENTS.md` was
deleted on 2026-10-02 ("Docs and formatting cleanup", commit `5b3028f`); this
file starts a new list rather than resurrecting old numbering. Known
owner-blocked item (Docker build needing an `ASTK_PAT` secret) is intentionally
not relisted here - it isn't actionable from a PR.

## 1. `api/database.py` / `api/main.py` hard-imported `astk` with no fallback, mislabeling 23 test skips (done 2026-10-12)

- [x] Fixed - see PR, (done 2026-10-12)

**What was wrong:** `src/config.py` and `src/alert_manager.py` both degrade
gracefully when the private `astk` package isn't installed (`try: from astk...
except ModuleNotFoundError:` with a documented fallback). `api/database.py`
(`from astk.db import make_engine`) and `api/main.py` (`from astk.db import
healthcheck`) did not - a bare import with no fallback. In the lightweight CI
install (and this sandbox), `astk` genuinely isn't available, so importing
either module raised `ModuleNotFoundError`. `tests/conftest.py`'s `client`
fixture caught that as a plain `except ImportError` and skipped every test in
`tests/test_api.py` with `pytest.skip("fastapi not installed - skipping API
tests")` - but fastapi *was* installed (CI installs it explicitly); the real
cause was the missing `astk`, and the skip message said otherwise, hiding the
real reason 22 tests never ran, plus the same misleading label on each one.

**Why it matters:** 22 of `tests/test_api.py`'s tests (the entire API test
suite) were silently skipped on every CI run, with a reason that pointed
whoever read the log at the wrong fix. A real regression in any API route
would have shipped with CI green.

**How it was fixed:** Same pattern already proven in this repo at
`src/config.py` - `try: from astk.db import make_engine / healthcheck except
ModuleNotFoundError:` with a small fallback (`sqlalchemy.create_engine` with
`pool_pre_ping=True` and SQLite-safe `StaticPool`/`check_same_thread=False` for
the engine; a plain `SELECT 1` probe for the healthcheck) that mirrors the
behavior the astk version documents. Also tightened `conftest.py`'s skip
message to report the actual import error instead of assuming "fastapi".

**How to check it:** `pytest tests/ -v` - all 22 `test_api.py` tests plus the
two new regression tests in `TestAstkLessImport` now run and pass (84 passed
total vs. 61 before, 1 skip remains: `test_alert_manager.py`'s own
`pytest.importorskip("astk")`, which is correctly labeled since that module
really does need astk's `Alert`/`SlackNotifier` classes, not just an engine).

## 2. `GET /products/margins/latest` returns 500 whenever there's actually data

**What's wrong:** `api/routes/products.py`'s `get_latest_margins` selects
`CAST(mh.calc_date AS TEXT)` with no `AS calc_date` alias. The resulting dict
key is the literal SQL expression string (`"CAST(mh.calc_date AS TEXT)"`), not
`calc_date`. `MarginResponse` requires a `calc_date` field, which is therefore
always missing, so FastAPI raises `ResponseValidationError` (HTTP 500) on
every call where `margin_history` has at least one row for the latest date.
The one test that exercises this (`test_get_latest_margins_with_data`)
explicitly accepts `resp.status_code in (200, 500)`, with a comment noting the
500 is itself "a real finding" - i.e. the test was written to tolerate the bug
rather than catch it.

**Why it matters:** this is the dashboard's and the What-If flow's main read
of current margins. It silently 500s the moment there's real data, while the
empty-table case (`test_get_latest_margins_empty`) passes fine - so a smoke
test against an empty DB gives no signal that the route is broken.

**How to check a fix:** add `AS calc_date` to the `CAST(...)` column in the
SQL, then tighten `test_get_latest_margins_with_data`'s assertion from
`in (200, 500)` to `== 200` plus a check on the returned `calc_date` value -
it should fail loudly if the alias regresses.

## 3. `DELETE /products/{id}` reports success for a product that doesn't exist

**What's wrong:** `deactivate_product` in `api/routes/products.py` runs an
`UPDATE products SET active = false ... WHERE id = :pid` and unconditionally
returns `{"status": "deactivated", "product_id": product_id}`, with no check
of how many rows were affected. `update_product` (`PUT /products/{id}`, a few
lines above in the same file) does the equivalent check correctly - it
re-selects the row and 404s if it's missing. Delete never does the same check.

**Why it matters:** calling `DELETE /products/99999` returns `200
{"status": "deactivated", "product_id": 99999}` instead of `404`, which is a
misleading success response for an operation that did nothing - exactly the
kind of silently-wrong-but-confident response this repo's own conventions (see
`CLAUDE.md`-equivalent guidance in sibling repos) warn against.

**How to check a fix:** check `result.rowcount` (or re-`SELECT`) after the
`UPDATE`, 404 if zero rows changed, and add a
`test_deactivate_nonexistent_product_returns_404` alongside the existing
`test_update_nonexistent_product_returns_404`.

## 4. `.env.example` is missing three config knobs `src/config.py` actually reads

**What's wrong:** `src/config.py`'s astk-less fallback branch reads
`DEFAULT_ALERT_THRESHOLD_PCT`, `B2B_DISCOUNT_FACTOR` and
`PRICE_RETENTION_DAYS` from the environment (with defaults `40.0`, `0.85`,
`90`) - these back the margin-alert threshold, the 15% B2B discount, and the
daily-price retention window, all real operational knobs. None of the three
appear in `.env.example`, which only documents `POSTGRES_*`, `DATABASE_URL`,
`JWT_*`, `SLACK_WEBHOOK_URL`, `AIRFLOW_UID`, `API_*` and `DASHBOARD_PORT`.

**Why it matters:** an operator who wants to raise the alert threshold or
change the B2B discount from the documented `.env` surface has no way to know
these variables exist short of reading `src/config.py`'s source - exactly the
"undocumented config knob" gap this backlog has flagged before (confirmed
fresh: still true on current `main`).

**How to check a fix:** add the three vars (with their real defaults as
comments) to `.env.example`, and add a test mirroring
`tests/test_readme_claims.py`'s style that asserts every env var
`src/config.py` reads also appears as a key in `.env.example`.
