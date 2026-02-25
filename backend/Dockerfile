# Production-ready Dockerfile for Imperecta backend (Railway deploy)
FROM python:3.12-slim

# System dependencies for Playwright
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

# Playwright Chromium
RUN playwright install chromium && playwright install-deps

# Application code
COPY . .

# Port (Railway injects PORT at runtime; default for build metadata)
ARG PORT=8000
EXPOSE ${PORT}

# Migrations + uvicorn; PORT from Railway
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
