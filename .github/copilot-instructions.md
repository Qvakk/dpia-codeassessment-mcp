# Technical DPIA MCP Server
**Project:** MCP server for GDPR/DPIA analysis. Analyzes codebases for privacy risks and generates compliance reports.

## Tech Stack
- **Language:** Python 3.12+
- **MCP Framework:** `mcp` SDK for tool definitions
- **Vector Store:** ChromaDB for legal document search
- **Embeddings:** HuggingFace (local), OpenAI, or Azure OpenAI
- **Web Scraping:** BeautifulSoup4 + httpx
- **Scheduler:** APScheduler for daily updates
- **Transport:** stdio (default) or HTTP/SSE

## Architecture
- `server.py` - MCP tool definitions and handlers
- `vector_store.py` - ChromaDB semantic search (2,456 legal documents)
- `embeddings.py` - Multi-provider embedding service
- `documentation_scraper.py` - Web scraper for GDPR/Datatilsynet sources
- `scheduler.py` - Daily document refresh (02:00 UTC)
- `csv_loader.py` - Load legal sources from CSV
- `security.py` - Input sanitization and validation

## Available Tools (Already Implemented)
- `search_documentation` - Semantic search across GDPR, Datatilsynet, EDPB documents
- `analyze_codebase_for_dpia` - Static analysis for data processing patterns
- `assess_processing_risk` - Risk scoring algorithm (Likelihood × Severity × Sensitivity)
- `check_gdpr_compliance` - Verify GDPR Articles 5, 25, 32, 35
- `generate_dpia_template` - Create Datatilsynet-compliant report
- `recommend_safeguards` - Generate mitigation recommendations

## Code Style & Patterns
- Type hints required for all functions
- Async/await for I/O operations
- Input validation using `InputSanitizer` class
- Comprehensive logging (INFO level default)
- Error handling with specific exceptions
- Non-root user execution (appuser:1000)
- Environment-based configuration (no hardcoded secrets)

## Security Requirements
- OWASP MCP Top 10 compliance
- Path traversal prevention
- No code modification (read-only analysis)
- API key rotation support
- Audit logging for tool invocations
- TLS support for HTTP mode

## Development Priorities
1. Core MCP server setup with stdio transport
2. Vector store initialization with ChromaDB
3. Legal document indexing from `data/legal_sources.csv`
4. Basic pattern detection (encryption, auth, logging)
5. Risk scoring algorithm
6. Report generation (Markdown format)
7. HTTP transport mode (optional)

## When Writing Code
- Follow existing patterns in codebase
- Use `InputSanitizer` for all user inputs
- Log tool invocations and results
- Return structured responses (JSON/Markdown)
- Include GDPR article citations in output
- Test on sample codebases (Python, JavaScript, Java)
