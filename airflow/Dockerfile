# Airflow Dockerfile — based on official Airflow image
# The base image already has airflow installed in PATH.
# Do NOT pip install apache-airflow — it breaks the installation.
FROM apache/airflow:2.9.3-python3.11

USER root
# git is required to install the private analytics-service-toolkit (astk),
# a git+https dependency in requirements-airflow.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl git && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# Install ONLY the extra Python packages the DAGs need.
# Do NOT install apache-airflow here — it's already in the image.
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
# astk is a PRIVATE repo; pip needs a GitHub token to clone it. The token is a
# BuildKit secret (id=astk_pat) mounted readable by the airflow user (uid 50000).
# We rewrite github.com URLs with the token for the install, then delete the git
# config so no credential survives in the committed layer. docker compose passes
# the secret automatically (see docker-compose.yml); for a bare build use:
#   DOCKER_BUILDKIT=1 docker build --secret id=astk_pat,env=ASTK_PAT -f airflow/Dockerfile .
RUN --mount=type=secret,id=astk_pat,uid=50000 \
    sh -eu -c 'if [ -s /run/secrets/astk_pat ]; then \
        git config --global url."https://x-access-token:$(cat /run/secrets/astk_pat)@github.com/".insteadOf "https://github.com/"; \
      fi; \
      pip install --no-cache-dir -r /tmp/requirements-airflow.txt; \
      rm -f "$HOME/.gitconfig"'

# Ensure the airflow binary is in PATH
ENV PATH="/home/airflow/.local/bin:${PATH}"

# Pre-create target directories (defensive — prevents COPY failure on empty dirs)
RUN mkdir -p /opt/airflow/dags /opt/airflow/plugins /opt/airflow/src /opt/airflow/scripts

# Copy DAGs, plugins, src, and scripts
COPY airflow/dags/ /opt/airflow/dags/
COPY airflow/plugins/ /opt/airflow/plugins/
COPY src/ /opt/airflow/src/
COPY scripts/ /opt/airflow/scripts/

# Verify airflow is available
RUN airflow version
