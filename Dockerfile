FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PYTHONPATH=/app/src:/app/scripts
ENV STOCK_LOCAL_STORE_ROOT=/data/stock-kline-cache
ENV STOCK_KLINE_CACHE_DIR=/data/stock-kline-cache
ENV KLINE_SYNC_ENABLED=true
ENV KLINE_SYNC_CLOUD_PREFIX=stock-kline-cache/latest
ENV KLINE_SYNC_RESTORE_ON_START=false
ENV KLINE_SYNC_RESTORE_STRICT=false
ENV KLINE_SYNC_BACKUP_ON_START=false
ENV KLINE_SYNC_BACKUP_INTERVAL_SECONDS=1800
ENV KLINE_SYNC_BACKUP_ON_STOP=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt /app/
COPY config /app/config
COPY src /app/src
COPY scripts /app/scripts
COPY docs /app/docs

RUN mkdir -p /app/data /app/data/_meta /app/data/reports /app/data/reports/_meta /data/stock-kline-cache

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN chmod +x /app/scripts/container_bootstrap_and_run.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/container_bootstrap_and_run.sh"]
CMD ["uvicorn", "chanlun_api.app:app", "--host", "0.0.0.0", "--port", "8000"]