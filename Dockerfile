FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools first
RUN pip install --no-cache-dir --upgrade pip "setuptools>=70.0" wheel

# Copy project files for installation
COPY pyproject.toml .
COPY src/ ./src/

# Install dependencies from pyproject.toml (single source of truth)
RUN pip install --no-cache-dir -e .

# Add src to PYTHONPATH so the module is importable
ENV PYTHONPATH=/app/src

# Create data directory for ChromaDB
RUN mkdir -p /app/data/chroma_db

# Create non-root user for security (MCP-05: Insecure Configuration)
RUN useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CHROMA_PERSIST_DIRECTORY=/app/data/chroma_db
ENV UPDATE_INTERVAL_DAYS=7
ENV AUTO_UPDATE_ENABLED=true
ENV TRANSPORT=http
ENV HTTP_PORT=3000

# Expose HTTP port
EXPOSE 3000

# Expose volume for persistent data
VOLUME ["/app/data"]

# Switch to non-root user
USER appuser

# Healthcheck for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5.0)" || exit 1

# Run the MCP server
CMD ["python", "-m", "technical_dpia_mcp.server"]
