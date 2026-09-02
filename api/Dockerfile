# FastAPI Dockerfile
FROM python:3.11-slim

WORKDIR /app

# git is required to install the private analytics-service-toolkit (astk),
# which is a git+https dependency in requirements-api.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-api.txt /tmp/requirements.txt
# astk is a PRIVATE repo, so pip needs a GitHub token to clone it. The token is
# passed as a BuildKit secret (id=astk_pat) — never a build-arg, which would be
# baked into image history. We temporarily rewrite github.com URLs to include
# the token, install, then delete the git config so no credential survives in
# the committed layer. Build with:
#   DOCKER_BUILDKIT=1 docker build --secret id=astk_pat,env=ASTK_PAT -f api/Dockerfile .
# (docker compose passes it automatically — see docker-compose.yml).
RUN --mount=type=secret,id=astk_pat \
    sh -eu -c 'if [ -s /run/secrets/astk_pat ]; then \
        git config --global url."https://x-access-token:$(cat /run/secrets/astk_pat)@github.com/".insteadOf "https://github.com/"; \
      fi; \
      pip install --no-cache-dir -r /tmp/requirements.txt; \
      rm -f "$HOME/.gitconfig"'

# Pre-create target directories (defensive)
RUN mkdir -p /app/api /app/src /app/scripts

COPY api/ /app/api/
COPY src/ /app/src/
COPY scripts/ /app/scripts/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
