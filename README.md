# Technical DPIA MCP Server

An MCP server for **Data Protection Impact Assessment (DPIA)** analysis with semantic search over GDPR, Datatilsynet guidance, EDPB guidelines, and international data protection regulations.

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

### Test the Tool

```bash
# Available tools via MCP:
# - search_documentation
# - analyze_codebase_for_dpia
# - assess_processing_risk
# - check_gdpr_compliance
# - generate_dpia_template
# - recommend_safeguards

# Example query:
# "search_documentation" with query="GDPR Article 35 DPIA requirements"
```

## Features

- 🔍 Semantic search over GDPR, Datatilsynet, EDPB guidelines (12 authoritative sources)
- 🇳🇴 Norwegian compliance focus (Datatilsynet templates, Personopplysningsloven)
- 🤖 Multi-provider embeddings (HuggingFace local, OpenAI, Azure OpenAI)
- ⏰ Auto-updating legal documents (daily at 02:00 UTC)
- 🔌 Dual transport: stdio (local) or HTTP (remote)
- 🐳 Docker containerized, non-root user, minimal footprint

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
# Endpoints: /health, /sse
docker logs technical-dpia-mcp-http -f
```

## Legal Sources

13 authoritative sources indexed:
- **Norwegian:** Datatilsynet, Lovdata, NTNU
- **EU:** GDPR, EDPB guidelines, Schrems II decision
- **International:** NIST Privacy Framework

Configuration: `data/legal_sources.csv`

## DPIA Assessment

Complete DPIA in [DPIA.md](DPIA.md):
- ✅ GDPR Article 35 compliance
- ✅ Datatilsynet checklist
- ✅ Risk assessment (MEDIUM)
- ✅ Security safeguards

**Key:** No personal data processed. Only public legal documents indexed.

## Requirements

- Python 3.12+
- Docker & Docker Compose
- 512MB+ memory
