# Production-ready Dockerfile for Imperecta backend (Railway deploy)
FROM python:3.12-slim

# Pull all pending Debian security fixes (base image tags lag behind the
# archive: perl-base CVE-2026-8376/13221/42496, sqlite3, gzip et al. ship as
# +deb13uN updates), then system deps for Playwright and app
RUN apt-get update && apt-get dist-upgrade -y && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (pip itself first: PYSEC-2026-3721 fixed in 26.2)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Playwright: install Chromium and system deps (single command for Docker)
RUN playwright install --with-deps chromium

# Application code
COPY . .

# Port (Railway injects PORT at runtime; default for build metadata)
ARG PORT=8000
EXPOSE ${PORT}

# Run migrations then start app. Celery worker/beat override CMD with custom commands.
# Migrations need DDL rights: they run under DATABASE_URL_MIGRATIONS (postgres)
# while the app itself runs under DATABASE_URL (imperecta_app after the 9.5 flip).
CMD ["sh", "-c", "DATABASE_URL=${DATABASE_URL_MIGRATIONS:-$DATABASE_URL} alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
