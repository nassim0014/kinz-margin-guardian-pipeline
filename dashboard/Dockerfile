# Streamlit Dashboard Dockerfile
FROM python:3.11-slim

WORKDIR /app

# git is required to install the private analytics-service-toolkit (astk),
# which is a git+https dependency in requirements-dashboard.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements-dashboard.txt /tmp/requirements.txt
# astk is a PRIVATE repo, so pip needs a GitHub token to clone it. The token is
# passed as a BuildKit secret (id=astk_pat) — never a build-arg, which would be
# baked into image history. We temporarily rewrite github.com URLs to include
# the token, install, then delete the git config so no credential survives in
# the committed layer. Build with:
#   DOCKER_BUILDKIT=1 docker build --secret id=astk_pat,env=ASTK_PAT -f dashboard/Dockerfile .
# (docker compose passes it automatically — see docker-compose.yml).
RUN --mount=type=secret,id=astk_pat \
    sh -eu -c 'if [ -s /run/secrets/astk_pat ]; then \
        git config --global url."https://x-access-token:$(cat /run/secrets/astk_pat)@github.com/".insteadOf "https://github.com/"; \
      fi; \
      pip install --no-cache-dir -r /tmp/requirements.txt; \
      rm -f "$HOME/.gitconfig"'

# Pre-create target directories (defensive)
RUN mkdir -p /app/dashboard /app/src /app/.streamlit

COPY dashboard/ /app/dashboard/
COPY src/ /app/src/
COPY .streamlit/ /app/.streamlit/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
