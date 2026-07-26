# ═══════════════════════════════════════════════════════════
# Project Atlas — Dockerfile
# ═══════════════════════════════════════════════════════════
# Multi-stage build:
#   1. builder — install dependencies + pre-commit hooks
#   2. runner  — minimal runtime image
#
# Usage:
#   docker build -t project-atlas .
#   docker run -p 8501:8501 -v atlas_data:/app/data project-atlas
# ═══════════════════════════════════════════════════════════

# ── Stage 1: Builder ─────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies needed for compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runner ──────────────────────────────────────
FROM python:3.11-slim AS runner

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r atlas && useradd -r -g atlas -d /app -s /sbin/nologin atlas

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY .streamlit/ .streamlit/
COPY src/ src/
COPY app.py .
COPY .env.example .env.example

# Create data directory with proper permissions
RUN mkdir -p /app/data && chown -R atlas:atlas /app/data

# Switch to non-root user
USER atlas

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Expose Streamlit port
EXPOSE 8501

# Run Streamlit app (flags via ENV vars — overridable at runtime)
CMD ["streamlit", "run", "app.py"]
