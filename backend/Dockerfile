# ==============================================================================
# Multi-Stage Production Dockerfile for FastAPI RAG Platform Backend
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Dependencies
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip & install CPU-only PyTorch first to prevent downloading CUDA binaries (~2GB saved)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install application requirements
COPY backend/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir -r /build/requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install minimal runtime shared libraries (libpq for postgres, curl for healthcheck, ffmpeg for media)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Set working directory & environment
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create required persistent data directories and assign ownership
RUN mkdir -p /app/data/vector_store /app/data/uploads /app/backend && \
    chown -R appuser:appgroup /app

# Copy backend application source, alembic configurations, and entrypoint
COPY --chown=appuser:appgroup backend /app/backend

# Make entrypoint script executable
RUN chmod +x /app/backend/entrypoint.sh

# Expose backend port
EXPOSE 8000

# Health check using liveness probe (/health)
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root user
USER appuser

# Launch via production entrypoint
ENTRYPOINT ["/bin/sh", "/app/backend/entrypoint.sh"]
