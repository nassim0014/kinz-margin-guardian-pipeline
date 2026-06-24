# Airflow Dockerfile — based on official Airflow image
FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

USER airflow
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pre-create target directories so COPY never fails if a source
# directory is empty or missing (e.g. airflow/plugins has only .gitkeep)
RUN mkdir -p /opt/airflow/dags /opt/airflow/plugins /opt/airflow/src /opt/airflow/scripts

# Copy DAGs, plugins, src, and scripts
COPY airflow/dags/ /opt/airflow/dags/
COPY airflow/plugins/ /opt/airflow/plugins/
COPY src/ /opt/airflow/src/
COPY scripts/ /opt/airflow/scripts/
