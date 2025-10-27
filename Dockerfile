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
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy only requirements first for better caching
COPY pyproject.toml .

# Install dependencies directly from pyproject.toml
RUN pip install --no-cache-dir \
    "mcp>=1.3.0" \
    "httpx>=0.28.1" \
    "beautifulsoup4>=4.13.0" \
    "lxml>=5.3.0" \
    "chromadb>=0.6.4" \
    "sentence-transformers>=3.4.1" \
    "openai>=1.59.9" \
    "tiktoken>=0.8.0" \
    "apscheduler>=3.11.0" \
    "python-dotenv>=1.0.1" \
    "pydantic>=2.10.6" \
    "numpy>=2.2.4" \
    "typing-extensions>=4.13.0" \
    "starlette>=0.41.3" \
    "uvicorn>=0.34.0" \
    "sse-starlette>=2.2.1" \
    "pypdf>=5.1.0" \
    "requests>=2.32.0"

# Now copy source code
COPY src/ ./src/

# Add src to PYTHONPATH so the module is importable
ENV PYTHONPATH=/app/src:$PYTHONPATH

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
