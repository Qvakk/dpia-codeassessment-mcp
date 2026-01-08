# Technical DPIA MCP Server

An MCP server for **Data Protection Impact Assessment (DPIA)** analysis with semantic search over GDPR, Datatilsynet guidance, EDPB guidelines, and international data protection regulations.

## Lite Version

Looking for a lighter alternative? Check out **[dpia-lite-mcp](https://github.com/Qvakk/dpia-lite-mcp)** - a simplified version without sentence-transformers and ChromaDB dependencies. Perfect for lower memory environments or when you don't need semantic search.

## Quick Start

### Start Container (stdio mode - default)

```bash
docker-compose up -d
```

Container: `dpia-codeassessment-mcp`

### MCP Client Configuration

**VS Code / Claude Desktop** (`mcp.json`):
```json
{
  "mcpServers": {
    "technical-dpia-mcp": {
      "command": "docker",
      "args": [
        "exec", "-i", "dpia-codeassessment-mcp",
        "python", "-m", "technical_dpia_mcp.server"
      ]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `search_documentation` | Semantic search over GDPR, Datatilsynet, EDPB documents |
| `update_documentation` | Manually trigger documentation re-scrape and re-index |
| `analyze_codebase_for_dpia` | Scan code for personal data patterns, storage, third-party services |
| `assess_processing_risk` | Calculate risk matrix (Likelihood x Severity x Sensitivity) |
| `check_gdpr_compliance` | Generate GDPR Article 35 compliance checklist |
| `generate_dpia_template` | Create full DPIA document template (Norwegian/English) |
| `recommend_safeguards` | Get technical/organisational measure recommendations |

## Features

- Semantic search over GDPR, Datatilsynet, EDPB guidelines (12 authoritative sources)
- Norwegian compliance focus (Datatilsynet templates, Personopplysningsloven)
- Multi-provider embeddings (HuggingFace local, OpenAI, Azure OpenAI)
- Auto-updating legal documents (daily at 02:00 UTC)
- Dual transport: stdio (local) or HTTP (StreamableHTTP + SSE)
- Docker containerized, non-root user, minimal footprint

## Environment Configuration

Key variables in `.env`:

- `TRANSPORT`: `stdio` (local) or `http` (remote, port 3000)
- `USE_EMBEDDINGS`: `true` for semantic search, `false` for keyword-only
- `EMBEDDING_PROVIDER`: `huggingface` (recommended, local), `openai`, or `azure`
- `AUTO_UPDATE_ENABLED`: `true` for daily legal document updates
- `UPDATE_INTERVAL_DAYS`: Days between manual document updates (default: 7)

## Modes

### stdio Mode (Default - Local MCP)

```bash
# Start
docker-compose up -d

# View logs
docker logs dpia-codeassessment-mcp -f

# Stop
docker-compose down
```

### HTTP Mode (Remote Access)

```bash
# Start on port 3003
docker-compose --profile http up -d

# Container: technical-dpia-mcp-http
# Endpoints: 
#   - /health (health check)
#   - /mcp (StreamableHTTP - recommended)
#   - /sse (legacy SSE)
docker logs technical-dpia-mcp-http -f
```

**MCP Client Configuration (StreamableHTTP):**
```json
{
  "mcpServers": {
    "dpia-mcp": {
      "type": "streamable-http",
      "url": "http://localhost:3003/mcp"
    }
  }
}
```

**MCP Client Configuration (SSE - legacy):**
```json
{
  "mcpServers": {
    "dpia-mcp": {
      "type": "sse",
      "url": "http://localhost:3003/sse"
    }
  }
}
```

## Legal Sources

12 authoritative sources indexed:
- **Norwegian:** Datatilsynet, Lovdata, NTNU
- **EU:** GDPR, EDPB guidelines, Schrems II decision
- **International:** NIST Privacy Framework

Configuration: `data/legal_sources.csv`

## DPIA Assessment

Complete DPIA in [DPIA.md](DPIA.md):
- GDPR Article 35 compliance
- Datatilsynet checklist
- Risk assessment (MEDIUM)
- Security safeguards

**Key:** No personal data processed. Only public legal documents indexed.

## Requirements

- Python 3.12+
- Docker & Docker Compose
- 512MB+ memory (2GB recommended)
- 512MB+ memory
