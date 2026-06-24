# Airflow Dockerfile — based on official Airflow image
# The base image already has airflow installed in PATH.
# Do NOT pip install apache-airflow — it breaks the installation.
FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

USER airflow

# Install ONLY the extra Python packages the DAGs need.
# Do NOT install apache-airflow here — it's already in the image.
COPY requirements-airflow.txt /tmp/requirements-airflow.txt
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt

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
