# LifeOS Dockerfile
# Production-ready Python FastAPI application
#
# Multi-stage build for smaller image:
# - Builder stage: install dependencies
# - Production stage: copy only what's needed

# === Builder Stage ===
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn


# === Production Stage ===
FROM python:3.11-slim as production

# Create non-root user for security
RUN groupadd -r lifeos && useradd -r -g lifeos lifeos

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=lifeos:lifeos src/ ./src/
COPY --chown=lifeos:lifeos ui/ ./ui/

# Create data directory for SQLite
RUN mkdir -p /data && chown lifeos:lifeos /data

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8080
ENV DATABASE_URL=sqlite:////data/lifeos.db
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Gunicorn configuration
ENV GUNICORN_WORKERS=2
ENV GUNICORN_THREADS=4
ENV GUNICORN_TIMEOUT=120
ENV GUNICORN_KEEPALIVE=5

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Switch to non-root user
USER lifeos

# Run with gunicorn + uvicorn workers for production
# uvicorn.workers.UvicornWorker gives us async support with production-grade process management
CMD ["sh", "-c", "gunicorn src.api:app \
    --bind ${HOST}:${PORT} \
    --workers ${GUNICORN_WORKERS} \
    --threads ${GUNICORN_THREADS} \
    --timeout ${GUNICORN_TIMEOUT} \
    --keep-alive ${GUNICORN_KEEPALIVE} \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    --capture-output"]
