# Streamlit Dashboard Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Pre-create target directories (defensive — prevents COPY failure on empty dirs)
RUN mkdir -p /app/dashboard /app/src /app/.streamlit

COPY dashboard/ /app/dashboard/
COPY src/ /app/src/
COPY .streamlit/ /app/.streamlit/

EXPOSE 8501

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
