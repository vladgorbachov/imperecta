# Production-ready Dockerfile for Imperecta backend (Railway deploy)
# Uses official Playwright Python image: browsers and system deps pre-installed (avoids install-deps failures on slim)
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app

# Python dependencies (playwright version must match image browsers, see requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Port (Railway injects PORT at runtime; default for build metadata)
ARG PORT=8000
EXPOSE ${PORT}

# Migrations + uvicorn; PORT from Railway
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
