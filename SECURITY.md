# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Email: security@kinzoils.com
Response SLA: 48 hours acknowledgement, 5 business days assessment.

**Do not open a public GitHub issue for security vulnerabilities.**

---

## Security Architecture

### 1. Database Credentials

- **Storage:** `.env` file (gitignored), loaded via `os.environ`
- **Never hardcoded** in source code, Dockerfiles, or docker-compose.yml
- **Docker network:** PostgreSQL is not exposed to the host — only accessible within the `kinz-net` Docker network
- **Connection string:** Uses `postgresql+psycopg://` SQLAlchemy URL with credentials from env vars

### 2. JWT Authentication (FastAPI)

- **Algorithm:** HS256 (HMAC-SHA256)
- **Secret:** `JWT_SECRET` env var, minimum 32 bytes
- **Token expiry:** 60 minutes (configurable via `JWT_EXPIRE_MINUTES`)
- **All API endpoints** (except `/auth/token`, `/health`, `/`) require `Authorization: Bearer <token>`
- **Token verification:** signature + expiry checked on every request via `get_current_user` dependency

### 3. Slack Webhook

- **URL storage:** `SLACK_WEBHOOK_URL` env var, never logged
- **Transmission:** HTTPS POST to Slack incoming webhook
- **No credentials** in alert messages — only product name, margin %, and threshold

### 4. Docker Security

| Control | Implementation |
|---------|----------------|
| Network isolation | Postgres not exposed to host (internal Docker network only) |
| Image base | Official `python:3.11-slim` and `apache/airflow:2.9.3` |
| Non-root user | Airflow runs as `airflow` user (uid 50000) |
| Read-only volumes | DAGs, plugins, and scripts mounted as `:ro` |
| Secrets | All via `.env` file, never baked into images |

### 5. Input Validation

- **Pydantic schemas** on all API payloads:
  - `cogs_tnd > 0` (COGS must be positive)
  - `alert_threshold_pct` between 0 and 100
  - `name` min 1, max 255 characters
- **SQLAlchemy ORM** — all queries use parameterized statements (no raw string SQL)
- **Rate limiting:** `slowapi` on FastAPI (120 requests/min per IP)

### 6. Data Quality (Airflow DAG)

- **ShortCircuitOperator** validates `competitor_price > 0` and `cogs > 0` before margin calculation
- Invalid data skips downstream tasks (no negative margins, no false alerts)
- All task results logged to Airflow task logs for audit

---

## Secret Management Checklist

| Secret | Env Var | Used By | Rotated How |
|--------|---------|---------|-------------|
| Postgres password | `POSTGRES_PASSWORD` | All services | Change in `.env` + `docker compose down -v && up` |
| JWT signing key | `JWT_SECRET` | FastAPI | Change in `.env` + restart API |
| Slack webhook | `SLACK_WEBHOOK_URL` | Airflow DAG | Rotate in Slack app settings |
| API user password | `API_PASSWORD` | FastAPI auth | Change in `.env` + restart API |

---

## CI/CD Security

- GitHub Actions workflow only installs lightweight test dependencies
- No secrets exposed to CI (tests use in-memory mocks, not real DB)
- Docker images built from official base images
- `.env` is gitignored and never committed

---

## Contact

Maintainer: Nassim K. — nassim@kinzoils.com
