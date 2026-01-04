# Multi-stage build for quarion API
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Clone repository (can be overridden with build args)
ARG GIT_REPO=https://github.com/highwater-industries/qa-mgr.git
ARG GIT_BRANCH=main
RUN git clone --branch ${GIT_BRANCH} --depth 1 ${GIT_REPO} /app

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from builder (cloned from git)
COPY --from=builder /app /app

# Create non-root user
RUN useradd -m -u 1000 quarion && chown -R quarion:quarion /app
USER quarion

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/')" || exit 1

# Default command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
