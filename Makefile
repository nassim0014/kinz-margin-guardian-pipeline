# Makefile for the Kinz Margin Guardian Pipeline.

PYTHON ?= python3
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.PHONY: help setup up down test lint ruff check seed clean

help:
        @echo "Kinz Margin Guardian Pipeline — Makefile"
        @echo ""
        @echo "Targets:"
        @echo "  make setup   — create venv and install requirements.txt"
        @echo "  make up      — docker compose up (full stack)"
        @echo "  make down    — docker compose down"
        @echo "  make test    — run pytest suite"
        @echo "  make lint    — syntax-check all Python files
  make ruff    — run ruff linter (error-only rules)
  make check   — run test + ruff (full local CI gate)"
        @echo "  make seed    — seed the database with KINZ products"
        @echo "  make clean   — remove venv and caches"

setup: $(VENV)/bin/activate
        @echo "✅ Virtualenv ready at $(VENV)"

$(VENV)/bin/activate:
        $(PYTHON) -m venv $(VENV)
        $(PIP) install --upgrade pip
        $(PIP) install -r requirements.txt
        @echo "✅ Installed all dependencies"

up:
        docker compose up --build -d
        @echo "✅ Stack running — Airflow: http://localhost:8080 | API: http://localhost:8000/docs | Dashboard: http://localhost:8501"

down:
        docker compose down
        @echo "✅ Stack stopped"

test: setup
        $(VENV)/bin/pytest tests/ -v

lint:
        @find src api airflow dashboard scripts -name "*.py" -print0 | xargs -0 -n1 $(PYTHON) -m py_compile
        @echo "✅ All files compile cleanly"

ruff: setup
        @echo "🔍 Running ruff linter ..."
        $(VENV)/bin/ruff check src/ api/ tests/ dashboard/ airflow/
        @echo "✅ Ruff clean"

check: test ruff
        @echo "✅ All checks passed"

seed:
        docker compose exec api python scripts/seed_products.py
        @echo "✅ Database seeded with KINZ products"

clean:
        rm -rf $(VENV) __pycache__ .pytest_cache .mypy_cache
        @echo "✅ Cleaned"
