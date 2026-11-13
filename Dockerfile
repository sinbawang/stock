# 基础镜像默认走 DaoCloud 的 Docker Hub 镜像加速，避免云端构建匿名拉取 docker.io 触发 429 限流。
# 本地/云端如需换源，可覆盖：docker build --build-arg PYTHON_IMAGE=python:3.11-slim .
# 腾讯云 VPC 内构建也可用：--build-arg PYTHON_IMAGE=mirror.ccs.tencentyun.com/library/python:3.11-slim
ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim

# ============ 阶段 1：构建依赖 ============
FROM ${PYTHON_IMAGE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md requirements.txt /app/
COPY src /app/src

# 装到 /install，方便整体拷贝
RUN pip install --no-cache-dir --retries 5 --timeout 60 --upgrade pip \
    && pip install --no-cache-dir --retries 5 --timeout 60 --prefix=/install .


# ============ 阶段 2：运行时 ============
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONPATH=/app/src:/app/scripts \
    STOCK_LOCAL_STORE_ROOT=/data/stock-kline-cache \
    STOCK_KLINE_CACHE_DIR=/data/stock-kline-cache \
    KLINE_SYNC_ENABLED=true \
    KLINE_SYNC_CLOUD_PREFIX=stock-kline-cache/latest \
    KLINE_SYNC_RESTORE_ON_START=true \
    KLINE_SYNC_RESTORE_STRICT=false \
    KLINE_SYNC_BACKUP_ON_START=false \
    KLINE_SYNC_BACKUP_INTERVAL_SECONDS=1800 \
    KLINE_SYNC_BACKUP_ON_STOP=true

WORKDIR /app

# 只拷依赖产物，不带 gcc
COPY --from=builder /install /usr/local

# 业务代码（docs 不要）
COPY config /app/config
COPY src /app/src
COPY scripts /app/scripts

RUN mkdir -p /app/data /app/data/_meta /app/data/reports /app/data/reports/_meta /data/stock-kline-cache \
    && chmod +x /app/scripts/container_bootstrap_and_run.sh

EXPOSE 8000

ENTRYPOINT ["/app/scripts/container_bootstrap_and_run.sh"]
CMD ["uvicorn", "chanlun_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
