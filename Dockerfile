# Multi-stage build for smaller final image
FROM python:3.11-slim-bookworm AS builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Final stage
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    # MCP Server settings
    LOG_LEVEL=INFO \
    LOG_FORMAT=json \
    API_SPORTS_API_KEY="" \
    HTTP_HOST=0.0.0.0 \
    HTTP_PORT=8080

# Create non-root user
RUN groupadd -r mcp && useradd -r -g mcp -m mcp

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=mcp:mcp mcp_server_api_sports /app/mcp_server_api_sports
COPY --chown=mcp:mcp pyproject.toml /app/

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && \
    chown -R mcp:mcp /app/logs && \
    chmod 755 /app/logs

# Switch to non-root user
USER mcp

# Expose port
EXPOSE 8000

# Health check disabled - FastMCP streamable-http doesn't easily support custom health endpoints
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command - run HTTP server with FastMCP
CMD ["python", "-m", "mcp_server_api_sports.server_fastmcp", "--http"]