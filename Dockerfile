# Vaultrix Production Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt pyproject.toml setup.py ./
COPY vaultrix/ ./vaultrix/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt && \
    pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .

# Stage 2: Runtime
FROM python:3.11-slim

LABEL maintainer="Vaultrix Team <team@vaultrix.dev>"
LABEL description="Vaultrix - Secure Autonomous AI Framework"
LABEL version="0.1.0"

# Create non-root user
RUN useradd -m -u 1000 vaultrix && \
    mkdir -p /workspace /home/vaultrix/.vaultrix && \
    chown -R vaultrix:vaultrix /workspace /home/vaultrix

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy wheels from builder
COPY --from=builder /wheels /wheels

# Install Vaultrix and dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY --chown=vaultrix:vaultrix vaultrix/ ./vaultrix/
COPY --chown=vaultrix:vaultrix examples/ ./examples/
COPY --chown=vaultrix:vaultrix README.md LICENSE ./

# Switch to non-root user
USER vaultrix

# Expose port for potential web UI (Phase 3+)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from vaultrix import VaultrixAgent; print('healthy')" || exit 1

# Default command
CMD ["vaultrix", "info"]
