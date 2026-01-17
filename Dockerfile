# =============================================================================
# Dockerfile for Worklog Application
# =============================================================================
# Multi-stage build for optimal image size and security
# Builds both React frontend and Python backend into a single container

# =============================================================================
# Stage 1: Frontend Builder (Node.js)
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy package files first for better layer caching
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build the React app (output goes to /frontend/dist)
RUN npm run build

# =============================================================================
# Stage 2: Backend Builder (Python)
# =============================================================================
FROM python:3.11-slim AS backend-builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY sql/ sql/

# Install dependencies
RUN uv pip install --system --no-cache .

# =============================================================================
# Stage 3: Production Image
# =============================================================================
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy installed packages from backend builder
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=backend-builder /app/src /app/src
COPY --from=backend-builder /app/sql /app/sql

# Copy built React frontend to static directory
# The FastAPI app expects static files at /app/static
COPY --from=frontend-builder /frontend/dist /app/static

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8000
ENV WORKERS=2
ENV STATIC_DIR=/app/static

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application with uvicorn (2 workers for resilience)
CMD ["python", "-m", "uvicorn", "worklog_app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
