# Production-ready Dockerfile for Imperecta backend (Railway deploy)
FROM python:3.12-slim

# System deps for Playwright and app
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright: install Chromium and system deps (single command for Docker)
RUN playwright install --with-deps chromium

# Application code
COPY . .

# Port (Railway injects PORT at runtime; default for build metadata)
ARG PORT=8000
EXPOSE ${PORT}

# Run migrations then start app. Tables also created by lifespan (create_all) as fallback.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
