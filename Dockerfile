FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt /app/
COPY src /app/src
COPY scripts /app/scripts
COPY docs /app/docs
COPY data /app/data

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "chanlun_api.app:app", "--host", "0.0.0.0", "--port", "8000"]