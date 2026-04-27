# UmaBuild backend container for Cloud Run.
# Build context is `backend/`. The feature_table_cache.parquet (~70 MB)
# is committed under data/ and copied in so the preflight 503 doesn't
# trigger on a cold container.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System libs LightGBM / pyarrow want at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy application code. data/feature_table_cache.parquet is whitelisted
# in .gitignore and required at runtime; .dockerignore must NOT exclude it.
COPY . .

# Cloud Run injects PORT (default 8080).
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
