# Firmia MCP Server - Production Dockerfile
# Multi-stage build for optimized image size

# Build stage
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim AS production

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r firmia && useradd -r -g firmia firmia

# Create necessary directories
RUN mkdir -p /data /logs/audit && \
    chown -R firmia:firmia /data /logs

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/firmia/.local

# Copy application code
COPY --chown=firmia:firmia src ./src
COPY --chown=firmia:firmia pyproject.toml .

# Set Python path
ENV PYTHONPATH=/app
ENV PATH=/home/firmia/.local/bin:$PATH

# Switch to non-root user
USER firmia

# Expose MCP server port
EXPOSE 8789

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8789/health').raise_for_status()"

# Run the MCP server
CMD ["python", "-m", "src.server"]