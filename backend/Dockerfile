FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENV=prod

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

COPY . .

RUN chmod +x start.sh

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

RUN mkdir -p /app/uploads /app/logs /tmp/uploads && \
    chown -R appuser:appuser /app/uploads /app/logs && \
    chmod 777 /tmp/uploads

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/health || exit 1

CMD ["./start.sh"]

