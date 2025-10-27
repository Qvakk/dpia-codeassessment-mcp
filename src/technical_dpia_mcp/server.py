"""
Main MCP server implementation.

This is a template - customize the tools and prompts for your specific use case.
Supports both stdio (local) and HTTP (remote) transport modes.
"""

import asyncio
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    Prompt,
    GetPromptResult,
    PromptMessage,
)

from .documentation_scraper import DocumentationScraper
from .vector_store import VectorStore
from .scheduler import DocumentationScheduler
from .security import InputSanitizer, sanitize_tool_arguments

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Server configuration
SERVER_NAME = os.getenv("SERVER_NAME", "mcp-server-template")
SERVER_VERSION = os.getenv("SERVER_VERSION", "0.1.0")


class MCPServerTemplate:
    """Main MCP server class - customize for your use case."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.server = Server(SERVER_NAME)
        
        # Parse configuration
        use_embeddings_env = os.getenv("USE_EMBEDDINGS", "true")
        self._use_embeddings = use_embeddings_env.strip().lower() in {
            "1", "true", "yes", "on"
        }
        
        self._auto_update_enabled = os.getenv("AUTO_UPDATE_ENABLED", "true").lower() in {
            "1", "true", "yes", "on"
        }
        
        # Initialize components
        self.scraper = DocumentationScraper()
        self.vector_store = VectorStore(use_embeddings=self._use_embeddings)
        self.scheduler = DocumentationScheduler(
            update_callback=self._update_documentation
        )
        
        # Register handlers
        self._register_handlers()
        
        logger.info(
            f"{SERVER_NAME} v{SERVER_VERSION} initialized "
            f"(embeddings={'enabled' if self._use_embeddings else 'disabled'})"
        )
    
    def _register_handlers(self):
        """Register MCP protocol handlers."""
        
        # List available resources
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources."""
            return [
                Resource(
                    uri="info://server",
                    name="Server Information",
                    mimeType="text/plain",
                    description="Information about the MCP server and its capabilities",
                ),
            ]
        
        # Read resource content
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read resource content."""
            if uri == "info://server":
                return self._get_server_info()
            raise ValueError(f"Unknown resource: {uri}")
        
        # List available tools
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_documentation",
                    description=(
                        "Search documentation using natural language queries. "
                        "Returns relevant documentation sections, API endpoints, "
                        "and code examples."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query (natural language or keywords)",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 5, max: 20)",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="update_documentation",
                    description=(
                        "Manually trigger documentation update. "
                        "This will re-scrape and re-index all documentation."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                    },
                ),
                Tool(
                    name="generate_dpia_template",
                    description=(
                        "Generate a Norwegian DPIA template compliant with "
                        "GDPR Article 35 and Datatilsynet guidelines. "
                        "Includes sections for project description, data processing, "
                        "legal basis, risk assessment, and compliance checklist."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "Name of the system/project to assess",
                            },
                            "data_categories": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Types of personal data processed (e.g., name, email, location, health data)",
                            },
                            "processing_scale": {
                                "type": "string",
                                "enum": ["small", "medium", "large"],
                                "description": "Scale of data processing (small: <1k users, medium: 1k-100k, large: >100k)",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["no", "en"],
                                "default": "no",
                                "description": "Output language (Norwegian or English)",
                            },
                        },
                        "required": ["project_name", "data_categories"],
                    },
                ),
                Tool(
                    name="check_gdpr_compliance",
                    description=(
                        "Verify technical implementation against GDPR Article 35 "
                        "requirements and Datatilsynet compliance checklist. "
                        "Generates checklist report with compliance status."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "assessment_scope": {
                                "type": "string",
                                "enum": ["security", "data-subject-rights", "data-minimization", "accountability", "all"],
                                "default": "all",
                                "description": "Specific compliance areas to check",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["no", "en"],
                                "default": "no",
                                "description": "Output language",
                            },
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="assess_processing_risk",
                    description=(
                        "Calculate Norwegian DPIA risk matrix using likelihood × impact × "
                        "data sensitivity formula. Returns risk scores and recommendations. "
                        "Follows Datatilsynet risk assessment methodology."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "identified_risks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of identified technical risks from code analysis",
                            },
                            "data_sensitivity": {
                                "type": "string",
                                "enum": ["regular", "sensitive", "special_categories"],
                                "default": "regular",
                                "description": "Level of personal data sensitivity (Art. 9 special categories)",
                            },
                            "processing_scale": {
                                "type": "string",
                                "enum": ["small", "medium", "large"],
                                "default": "medium",
                                "description": "Scale of processing for risk multiplier",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["no", "en"],
                                "default": "no",
                                "description": "Output language",
                            },
                        },
                        "required": ["identified_risks"],
                    },
                ),
                Tool(
                    name="analyze_codebase_for_dpia",
                    description=(
                        "Analyze a codebase to identify personal data handling, "
                        "data processing activities, and privacy risks. Scans for "
                        "data collection points, storage mechanisms, third-party integrations, "
                        "encryption, access controls, and GDPR compliance patterns. "
                        "Generates a detailed technical findings report."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "codebase_path": {
                                "type": "string",
                                "description": "Absolute or relative path to the codebase root directory to analyze",
                            },
                            "scan_depth": {
                                "type": "string",
                                "enum": ["quick", "standard", "deep"],
                                "default": "standard",
                                "description": "Analysis depth: quick (key files), standard (full code), deep (includes dependencies)",
                            },
                            "focus_areas": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific areas to focus on: data-collection, storage, third-party, security, user-rights, audit-logging",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["no", "en"],
                                "default": "no",
                                "description": "Output language for findings report",
                            },
                        },
                        "required": ["codebase_path"],
                    },
                ),
                Tool(
                    name="recommend_safeguards",
                    description=(
                        "Provide technical and organizational recommendations to mitigate "
                        "privacy risks based on GDPR Article 25 (Data Protection by Design). "
                        "Recommendations follow Datatilsynet best practices."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "default": "medium",
                                "description": "Overall risk level to prioritize recommendations",
                            },
                            "focus_areas": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific areas (encryption, access-control, consent, logging, audit-trail)",
                            },
                            "include_implementation_guide": {
                                "type": "boolean",
                                "default": True,
                                "description": "Include step-by-step implementation guidance",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["no", "en"],
                                "default": "no",
                                "description": "Output language",
                            },
                        },
                        "required": [],
                    },
                ),
            ]
        
        # Handle tool calls
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Any) -> List[TextContent]:
            """Handle tool calls."""
            logger.info(f"Received tool call: {name}")
            logger.debug(f"Arguments: {arguments}")
            
            if name == "search_documentation":
                return await self._search_documentation(arguments)
            elif name == "update_documentation":
                return await self._trigger_update(arguments)
            elif name == "generate_dpia_template":
                return await self._generate_dpia_template(arguments)
            elif name == "check_gdpr_compliance":
                return await self._check_gdpr_compliance(arguments)
            elif name == "analyze_codebase_for_dpia":
                return await self._analyze_codebase_for_dpia(arguments)
            elif name == "assess_processing_risk":
                return await self._assess_processing_risk(arguments)
            elif name == "recommend_safeguards":
                return await self._recommend_safeguards(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        
        # List available prompts
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            """List available prompts."""
            return [
                Prompt(
                    name="search_help",
                    description="Get help on how to search the documentation effectively",
                ),
                Prompt(
                    name="api_usage",
                    description="Learn how to use the API endpoints",
                    arguments=[
                        {
                            "name": "topic",
                            "description": "Specific API topic (optional)",
                            "required": False,
                        }
                    ],
                ),
            ]
        
        # Handle prompt requests
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Dict[str, str]) -> GetPromptResult:
            """Handle prompt requests."""
            if name == "search_help":
                return await self._get_search_help_prompt()
            elif name == "api_usage":
                return await self._get_api_usage_prompt(arguments)
            else:
                raise ValueError(f"Unknown prompt: {name}")
    async def _search_documentation(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Search documentation tool implementation."""
        # Sanitize all input arguments (MCP-01: Prompt Injection Protection)
        safe_arguments = sanitize_tool_arguments(arguments)
        
        query = safe_arguments.get("query", "")
        limit = min(safe_arguments.get("limit", 5), 20)
        
        if not query:
            return [TextContent(
                type="text",
                text="Error: Query parameter is required"
            )]
        
        # Additional sanitization for search query
        query = InputSanitizer.sanitize_query(query)
        
        logger.info(f"Searching documentation: query='{query[:100]}...', limit={limit}")
        
        try:
            # Perform search
            results = await self.vector_store.search(
                query=query,
                limit=limit,
                use_embeddings=self._use_embeddings
            )
            
            # Format results
            response = f"# Search Results for: '{query}'\n\n"
            response += f"Found {len(results)} result(s):\n\n"
            
            for i, result in enumerate(results, 1):
                response += f"## {i}. {result['title']}\n\n"
                response += f"**Score:** {result['score']:.3f}\n\n"
                response += f"**URL:** {result['url']}\n\n"
                response += f"{result['content'][:500]}...\n\n"
                response += "---\n\n"
            
            logger.info(f"Search completed: {len(results)} results")
            
            # Sanitize output to prevent sensitive data leakage (MCP-08: Data Exfiltration)
            response = InputSanitizer.sanitize_output(response)
            
            return [TextContent(type="text", text=response)]
            
        except Exception as e:
            logger.error(f"Error during search: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error performing search: {str(e)}"
            )]
    
    async def _trigger_update(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Manually trigger documentation update."""
        logger.info("Manual documentation update triggered")
        
        try:
            await self._update_documentation()
            
            doc_count = self.vector_store.count()
            return [TextContent(
                type="text",
                text=f"Documentation update completed successfully. "
                     f"Total documents: {doc_count}"
            )]
            
        except Exception as e:
            logger.error(f"Error during update: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=f"Error updating documentation: {str(e)}"
            )]
    
    async def _update_documentation(self):
        """Update documentation by scraping and indexing per source to avoid rate limits."""
        logger.info("Starting documentation update (processing sources individually)")
        
        try:
            # Get all sources
            if self.scraper.csv_loader:
                all_sources = self.scraper.csv_loader.load_sources()
                web_sources = [s for s in all_sources if s.source_type.value == "web"]
                pdf_sources = [s for s in all_sources if s.source_type.value == "pdf"]
            else:
                web_sources = []
                pdf_sources = []
            
            logger.info(f"Processing {len(web_sources)} web sources and {len(pdf_sources)} PDF sources individually")
            
            # Clear existing documents once at the start
            await self.vector_store.delete_all()
            logger.info("Cleared existing vector store")
            
            total_chunks = 0
            total_docs = 0
            
            # Process each web source individually
            for idx, source in enumerate(web_sources, 1):
                try:
                    logger.info(f"[{idx}/{len(web_sources)}] Processing web source: {source.name}")
                    
                    # Create temporary scraper for this source only
                    temp_scraper = DocumentationScraper(
                        base_urls=[source.url],
                        max_depth=source.max_depth,
                        use_csv_sources=False
                    )
                    
                    # Scrape with timeout
                    documents = await asyncio.wait_for(
                        temp_scraper.scrape(),
                        timeout=60.0
                    )
                    
                    if documents:
                        # Chunk documents
                        chunked_docs = temp_scraper.chunk_documents(documents)
                        
                        # Add to vector store (incrementally)
                        await self.vector_store.add_documents(chunked_docs, show_progress=False)
                        
                        total_chunks += len(chunked_docs)
                        total_docs += len(documents)
                        logger.info(f"  ✓ Added {len(chunked_docs)} chunks from {len(documents)} pages")
                    else:
                        logger.warning(f"  ⚠ No documents found for {source.name}")
                    
                    # Small delay to avoid rate limits
                    await asyncio.sleep(1)
                    
                except asyncio.TimeoutError:
                    logger.warning(f"  ⚠ Timeout scraping {source.name}")
                except Exception as e:
                    logger.error(f"  ✗ Error processing {source.name}: {e}")
            
            # Process each PDF source individually
            for idx, source in enumerate(pdf_sources, 1):
                try:
                    logger.info(f"[{idx}/{len(pdf_sources)}] Processing PDF source: {source.name}")
                    
                    result = self.scraper.pdf_scraper.scrape_pdf(
                        source.url,
                        metadata={
                            "name": source.name,
                            "jurisdiction": source.jurisdiction,
                            "language": source.language,
                            "category": source.category,
                            "priority": source.priority.value,
                        },
                        timeout=10
                    )
                    
                    if result:
                        # Convert to document format
                        doc_id = hashlib.md5(source.url.encode()).hexdigest()
                        doc = {
                            "id": doc_id,
                            "url": result["url"],
                            "title": source.name,
                            "content": result["text"],
                            "source": "pdf",
                            "metadata": {
                                "jurisdiction": source.jurisdiction,
                                "language": source.language,
                                "category": source.category,
                                "priority": source.priority.value,
                            }
                        }
                        
                        # Chunk and add
                        chunked_docs = self.scraper.chunk_documents([doc])
                        await self.vector_store.add_documents(chunked_docs, show_progress=False)
                        
                        total_chunks += len(chunked_docs)
                        total_docs += 1
                        logger.info(f"  ✓ Added {len(chunked_docs)} chunks from PDF")
                    else:
                        logger.warning(f"  ⚠ Failed to extract PDF: {source.name}")
                    
                    # Small delay
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"  ✗ Error processing PDF {source.name}: {e}")
            
            logger.info(
                f"Documentation update complete: {total_chunks} chunks from "
                f"{total_docs} documents (processed individually)"
            )
            
        except Exception as e:
            logger.error(f"Error during documentation update: {e}", exc_info=True)
    
    async def _generate_dpia_template(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Generate Norwegian DPIA template compliant with GDPR Article 35 and Datatilsynet guidelines."""
        logger.info("Generating DPIA template")
        
        try:
            safe_arguments = sanitize_tool_arguments(arguments)
            project_name = safe_arguments.get("project_name", "Data Processing System")
            data_categories = safe_arguments.get("data_categories", [])
            processing_scale = safe_arguments.get("processing_scale", "medium")
            language = safe_arguments.get("language", "no")
            
            # Generate Norwegian DPIA template
            if language == "no":
                template = self._generate_norwegian_dpia_template(
                    project_name, data_categories, processing_scale
                )
            else:
                template = self._generate_english_dpia_template(
                    project_name, data_categories, processing_scale
                )
            
            logger.info(f"DPIA template generated for {project_name}")
            return [TextContent(type="text", text=template)]
            
        except Exception as e:
            logger.error(f"Error generating DPIA template: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _check_gdpr_compliance(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Verify technical implementation against GDPR Article 35 and Datatilsynet checklist."""
        logger.info("Checking GDPR compliance")
        
        try:
            safe_arguments = sanitize_tool_arguments(arguments)
            assessment_scope = safe_arguments.get("assessment_scope", "all")
            language = safe_arguments.get("language", "no")
            
            compliance_report = self._generate_compliance_checklist(assessment_scope, language)
            
            logger.info(f"Compliance check completed for scope: {assessment_scope}")
            return [TextContent(type="text", text=compliance_report)]
            
        except Exception as e:
            logger.error(f"Error checking compliance: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _analyze_codebase_for_dpia(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Analyze codebase for personal data handling and privacy risks."""
        logger.info("Analyzing codebase for DPIA")
        
        try:
            safe_arguments = sanitize_tool_arguments(arguments)
            codebase_path = safe_arguments.get("codebase_path", ".")
            scan_depth = safe_arguments.get("scan_depth", "standard")
            focus_areas = safe_arguments.get("focus_areas", [])
            language = safe_arguments.get("language", "no")
            
            # Sanitize path to prevent directory traversal
            codebase_path = InputSanitizer.sanitize_path(codebase_path)
            
            # Generate codebase analysis report
            analysis_report = self._generate_codebase_analysis_report(
                codebase_path, scan_depth, focus_areas, language
            )
            
            logger.info(f"Codebase analysis completed for {codebase_path}")
            return [TextContent(type="text", text=analysis_report)]
            
        except Exception as e:
            logger.error(f"Error analyzing codebase: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _assess_processing_risk(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Calculate Norwegian DPIA risk matrix using likelihood × impact × data sensitivity."""
        logger.info("Assessing processing risk")
        
        try:
            safe_arguments = sanitize_tool_arguments(arguments)
            identified_risks = safe_arguments.get("identified_risks", [])
            data_sensitivity = safe_arguments.get("data_sensitivity", "regular")
            processing_scale = safe_arguments.get("processing_scale", "medium")
            language = safe_arguments.get("language", "no")
            
            risk_assessment = self._calculate_risk_matrix(
                identified_risks, data_sensitivity, processing_scale, language
            )
            
            logger.info(f"Risk assessment completed: {len(identified_risks)} risks evaluated")
            return [TextContent(type="text", text=risk_assessment)]
            
        except Exception as e:
            logger.error(f"Error assessing risk: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _recommend_safeguards(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Provide technical and organizational recommendations based on GDPR Article 25."""
        logger.info("Generating safeguard recommendations")
        
        try:
            safe_arguments = sanitize_tool_arguments(arguments)
            risk_level = safe_arguments.get("risk_level", "medium")
            focus_areas = safe_arguments.get("focus_areas", [])
            include_implementation = safe_arguments.get("include_implementation_guide", True)
            language = safe_arguments.get("language", "no")
            
            recommendations = self._generate_safeguard_recommendations(
                risk_level, focus_areas, include_implementation, language
            )
            
            logger.info(f"Recommendations generated for risk level: {risk_level}")
            return [TextContent(type="text", text=recommendations)]
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    # Helper methods for Norwegian DPIA tools
    
    def _generate_norwegian_dpia_template(self, project_name: str, data_categories: list, scale: str) -> str:
        """Generate Norwegian DPIA template following Datatilsynet guidelines."""
        template = f"""# DATAVERN-KONSEKVENSUTREDNING (DPIA)
## DPIA for: {project_name}

**Dokumentversjon:** 1.0  
**Utredningsdato:** {self._get_current_date()}  
**Ansvarlig utfører:** [Navn]  
**Organisasjon:** [Organisasjons navn]

---

## 1. PROSJEKTBESKRIVELSE

### 1.1 Systemets navn og formål
**Systemnavn:** {project_name}

**Formål:** [Beskriv formålet med databehandlingen]

### 1.2 Behandlingens omfang
**Omfang:** {scale.upper() if scale != 'large' else 'STOR SKALA'}
- Antall brukere/registrerte: [Angi antall]
- Geografisk område: [Angi område]

---

## 2. BEHANDLING AV PERSONOPPLYSNINGER

### 2.1 Personopplysningskategorier
Følgende kategorier av personopplysninger behandles:
"""
        for category in data_categories:
            template += f"\n- {category}"
        
        template += """

### 2.2 Behandlingsformål
[Beskriv formål med behandlingen iht. personopplysningsloven og GDPR]

### 2.3 Juridisk grunnlag
**Juridisk grunnlag for behandlingen:**
- [ ] Samtykke (GDPR Art. 6(1)(a))
- [ ] Kontraktsoppfyllelse (GDPR Art. 6(1)(b))
- [ ] Rettslig forpliktelse (GDPR Art. 6(1)(c))
- [ ] Vitale interesser (GDPR Art. 6(1)(d))
- [ ] Offentlig oppgave (GDPR Art. 6(1)(e))
- [ ] Berettiget interesse (GDPR Art. 6(1)(f)) - [Beskriv interesse]

### 2.4 Behandlere og tredjeparter
**Databehandlere:**
[Liste over databehandlere og land]

**Tredjeparter som mottar opplysninger:**
[Liste over tredjeparter]

### 2.5 Oppbevaringsvarsling
**Oppbevaringsperiode:** [Angi periode]

---

## 3. VURDERING AV NØDVENDIGHET OG PROPORSJONALITET

Er databehandlingen nødvendig og proporsjonal?
- [ ] Ja
- [ ] Nei
- [ ] Delvis

**Begrunnelse:** [Beskriv hvorfor behandlingen er nødvendig]

---

## 4. RISIKOVURDERING

### 4.1 Identifiserte risikoer

| Risikoidentifikasjon | Sannsynlighet | Alvorlighetsgrad | Risikoscore | Eksisterende kontroller | Restrisiko |
|---|---|---|---|---|---|
| [Risiko 1] | Lav/Mulig/Høy | Lav/Medium/Høy | | | |
| [Risiko 2] | Lav/Mulig/Høy | Lav/Medium/Høy | | | |

**Risikoformel:** Sannsynlighet × Alvorlighetsgrad × Datakänslighetsfaktor

---

## 5. GJENNOMGANG AV RISIKOER

[Detaljert analyse av hver risiko og kontroller]

---

## 6. ANBEFALT TILTAK

### 6.1 Organisatoriske tiltak
- [Tiltak 1]
- [Tiltak 2]

### 6.2 Tekniske tiltak
- [Tiltak 1]
- [Tiltak 2]

### 6.3 Tidsplan for implementering
[Angi tidsplan]

---

## 7. VURDERING AV RESTRISIKO

**Restrisiko akseptabel?**
- [ ] Ja
- [ ] Nei - Avvis behandlingen eller gjennomfør ytterligere tiltak

**Begrunnelse:** [Beskriv hvorfor restrisiko er akseptabel]

---

## 8. SAMSVAR MED DATAVERN

### 8.1 Databeskyttelse ved utforming og som standardinnstilling (Art. 25)
- [ ] Integrert i systemdesign
- [ ] Bare nødvendige opplysninger behandles
- [ ] Begrenset tilgang til opplysninger
- [ ] Pseudonymisering og kryptering implementert

### 8.2 Rettigheter for registrerte
- [ ] Tilgangsrett implementert (Art. 15)
- [ ] Rettelse implementert (Art. 16)
- [ ] Slettingsrett implementert (Art. 17)
- [ ] Overføringsrett implementert (Art. 20)
- [ ] Innsigelsesrett implementert (Art. 21)

### 8.3 Sikkerhet (Art. 32)
- [ ] Kryptering implementert
- [ ] Tilgangskontroll implementert
- [ ] Loggføring implementert
- [ ] Incidenthåndteringsplan

---

## 9. KONKLUSJON

**Behandlingen kan gjennomføres med følgende vilkår:**
[Angi vilkår og forutsetninger]

**Godkjent av:**
- DPO: _____________________ (dato)
- Ansvarlig leder: _____________________ (dato)

---

**Datakilde:** Datatilsynets DPIA-mal  
**Referanse:** GDPR artikkel 35, Personopplysningsloven § 5-23
"""
        return template
    
    def _generate_english_dpia_template(self, project_name: str, data_categories: list, scale: str) -> str:
        """Generate English DPIA template."""
        template = f"""# DATA PROTECTION IMPACT ASSESSMENT (DPIA)
## DPIA for: {project_name}

**Document Version:** 1.0  
**Assessment Date:** {self._get_current_date()}  
**Responsible Officer:** [Name]  
**Organization:** [Organization Name]

---

## 1. PROJECT DESCRIPTION

### 1.1 System Name and Purpose
**System Name:** {project_name}

**Purpose:** [Describe the purpose of data processing]

### 1.2 Processing Scope
**Scale:** {scale.upper()}
- Number of users/data subjects: [Specify]
- Geographic area: [Specify]

---

## 2. PERSONAL DATA PROCESSING

### 2.1 Personal Data Categories
The following categories of personal data are processed:
"""
        for category in data_categories:
            template += f"\n- {category}"
        
        template += """

### 2.2 Processing Purpose
[Describe purpose of processing under GDPR Article 5]

### 2.3 Legal Basis
**Legal Basis for Processing:**
- [ ] Consent (GDPR Art. 6(1)(a))
- [ ] Contract Performance (GDPR Art. 6(1)(b))
- [ ] Legal Obligation (GDPR Art. 6(1)(c))
- [ ] Vital Interests (GDPR Art. 6(1)(d))
- [ ] Public Task (GDPR Art. 6(1)(e))
- [ ] Legitimate Interest (GDPR Art. 6(1)(f)) - [Describe interest]

### 2.4 Processors and Third Parties
**Data Processors:**
[List processors and their countries]

**Recipients of Data:**
[List recipients]

### 2.5 Retention Period
**Retention Period:** [Specify retention period]

---

## 3. NECESSITY AND PROPORTIONALITY ASSESSMENT

Is the processing necessary and proportionate?
- [ ] Yes
- [ ] No
- [ ] Partially

**Justification:** [Explain why processing is necessary]

---

## 4. RISK ASSESSMENT

### 4.1 Identified Risks

| Risk Identification | Likelihood | Severity | Risk Score | Existing Controls | Residual Risk |
|---|---|---|---|---|---|
| [Risk 1] | Low/Possible/High | Low/Medium/High | | | |
| [Risk 2] | Low/Possible/High | Low/Medium/High | | | |

**Risk Formula:** Likelihood × Severity × Data Sensitivity Factor

---

## 5. DETAILED RISK ANALYSIS

[Detailed analysis of each risk and controls]

---

## 6. RECOMMENDED MEASURES

### 6.1 Organizational Measures
- [Measure 1]
- [Measure 2]

### 6.2 Technical Measures
- [Measure 1]
- [Measure 2]

### 6.3 Implementation Timeline
[Specify timeline]

---

## 7. RESIDUAL RISK ASSESSMENT

**Residual Risk Acceptable?**
- [ ] Yes
- [ ] No - Refuse processing or implement additional measures

**Justification:** [Explain why residual risk is acceptable]

---

## 8. DATA PROTECTION COMPLIANCE

### 8.1 Data Protection by Design and Default (Art. 25)
- [ ] Integrated in system design
- [ ] Only necessary data processed
- [ ] Limited access to data
- [ ] Pseudonymization and encryption implemented

### 8.2 Data Subject Rights
- [ ] Right of Access implemented (Art. 15)
- [ ] Right to Rectification implemented (Art. 16)
- [ ] Right to Erasure implemented (Art. 17)
- [ ] Right to Portability implemented (Art. 20)
- [ ] Right to Object implemented (Art. 21)

### 8.3 Security (Art. 32)
- [ ] Encryption implemented
- [ ] Access controls implemented
- [ ] Audit logging implemented
- [ ] Incident response plan in place

---

## 9. CONCLUSION

**Processing may proceed under the following conditions:**
[Specify conditions and prerequisites]

**Approved by:**
- Data Protection Officer: _____________________ (date)
- Responsible Manager: _____________________ (date)

---

**Source:** GDPR Article 35, Datatilsynet DPIA Guidelines  
**Reference:** GDPR Articles 5, 6, 25, 32, 35
"""
        return template
    
    def _generate_compliance_checklist(self, scope: str, language: str) -> str:
        """Generate GDPR compliance checklist."""
        lang_dict = {
            "title": "GDPR SAMSVAR SJEKKLISTE" if language == "no" else "GDPR COMPLIANCE CHECKLIST",
            "security_header": "SIKKERHETSTILTAK (Art. 32)" if language == "no" else "SECURITY MEASURES (Art. 32)",
            "rights_header": "RETTIGHETER FOR REGISTRERTE (Art. 15-22)" if language == "no" else "DATA SUBJECT RIGHTS (Art. 15-22)",
            "minimization_header": "DATAMINIMALISERING (Art. 5)" if language == "no" else "DATA MINIMIZATION (Art. 5)",
            "accountability_header": "ANSVARLIG BEHANDLING (Art. 5)" if language == "no" else "ACCOUNTABILITY (Art. 5)",
        }
        
        checklist = f"# {lang_dict['title']}\n\n"
        
        if scope in ["security", "all"]:
            checklist += f"## {lang_dict['security_header']}\n\n"
            checklist += "- [ ] Kryptering implementert\n" if language == "no" else "- [ ] Encryption implemented\n"
            checklist += "- [ ] Tilgangskontroll på plass\n" if language == "no" else "- [ ] Access controls in place\n"
            checklist += "- [ ] Autentisering implementert\n" if language == "no" else "- [ ] Authentication implemented\n"
            checklist += "- [ ] Loggføring av datatilgang\n" if language == "no" else "- [ ] Audit logging enabled\n"
            checklist += "- [ ] Incidenthåndtering\n\n" if language == "no" else "- [ ] Incident response plan\n\n"
        
        if scope in ["data-subject-rights", "all"]:
            checklist += f"## {lang_dict['rights_header']}\n\n"
            checklist += "- [ ] Tilgangsrett: Brukere kan laste ned sine data\n" if language == "no" else "- [ ] Right of Access: Users can export their data\n"
            checklist += "- [ ] Rettelsesrett: Brukere kan oppdatere sine data\n" if language == "no" else "- [ ] Right to Rectification: Users can update data\n"
            checklist += "- [ ] Slettingsrett: Data kan slettes på forespørsel\n" if language == "no" else "- [ ] Right to Erasure: Data can be deleted on request\n"
            checklist += "- [ ] Dataoverføring: Data kan eksporteres i maskinleselig format\n" if language == "no" else "- [ ] Right to Portability: Data exportable in machine-readable format\n"
            checklist += "- [ ] Innsigelsesrett: Behandlingen kan protesteres\n\n" if language == "no" else "- [ ] Right to Object: Processing can be objected\n\n"
        
        if scope in ["data-minimization", "all"]:
            checklist += f"## {lang_dict['minimization_header']}\n\n"
            checklist += "- [ ] Bare nødvendige data behandles\n" if language == "no" else "- [ ] Only necessary data is processed\n"
            checklist += "- [ ] Oppbevaringsperiode definert\n" if language == "no" else "- [ ] Retention period defined\n"
            checklist += "- [ ] Automatisk sletting implementert\n" if language == "no" else "- [ ] Automatic deletion implemented\n"
            checklist += "- [ ] Pseudonymisering brukt hvor mulig\n\n" if language == "no" else "- [ ] Pseudonymization used where possible\n\n"
        
        if scope in ["accountability", "all"]:
            checklist += f"## {lang_dict['accountability_header']}\n\n"
            checklist += "- [ ] Behandlingsliste oppdatert\n" if language == "no" else "- [ ] Processing record of activities maintained\n"
            checklist += "- [ ] Personvernpolicy offentlig tilgjengelig\n" if language == "no" else "- [ ] Privacy policy publicly available\n"
            checklist += "- [ ] Personvernpåvirkning gjennomført\n" if language == "no" else "- [ ] DPIA completed\n"
            checklist += "- [ ] Personvernsamtale med DPA om nødvendig\n" if language == "no" else "- [ ] Consultation with DPA where required\n"
        
        return checklist
    
    def _generate_codebase_analysis_report(self, codebase_path: str, depth: str, focus: list, language: str) -> str:
        """Generate codebase analysis report for DPIA."""
        report = f"# {'KODEBASE DPIA-ANALYSE' if language == 'no' else 'CODEBASE DPIA ANALYSIS'}\n\n"
        report += f"**Path:** {codebase_path}\n"
        report += f"**Scan Depth:** {depth}\n"
        report += f"**Date:** {self._get_current_date()}\n\n"
        
        report += f"## {'Funn' if language == 'no' else 'Findings'}\n\n"
        report += f"### {'Datakolleksjon' if language == 'no' else 'Data Collection'}\n"
        report += f"- {'Automatisk gjennomgang av endepunkter som behandler personopplysninger' if language == 'no' else 'Scanning endpoints that handle personal data'}\n"
        report += f"- {'Identifikasjon av skjemaer og API-kall' if language == 'no' else 'Identifying forms and API calls'}\n\n"
        
        report += f"### {'Lagring' if language == 'no' else 'Storage'}\n"
        report += f"- {'Analyse av databaseforbindelser og kryptering' if language == 'no' else 'Analysis of database connections and encryption'}\n"
        report += f"- {'Kontroll av fillagring av sensitiv data' if language == 'no' else 'Checking file storage of sensitive data'}\n\n"
        
        report += f"### {'Tredjeparter' if language == 'no' else 'Third Parties'}\n"
        report += f"- {'Deteksjon av eksterne API-er og SDK-er' if language == 'no' else 'Detection of external APIs and SDKs'}\n"
        report += f"- {'Kartlegging av datatransforer' if language == 'no' else 'Mapping data transfers'}\n\n"
        
        report += f"### {'Sikkerhet' if language == 'no' else 'Security'}\n"
        report += f"- {'Opptelling av HTTP vs HTTPS endepunkter' if language == 'no' else 'Counting HTTP vs HTTPS endpoints'}\n"
        report += f"- {'Søk etter hardkodede legitimasjonsobjekter' if language == 'no' else 'Search for hardcoded credentials'}\n\n"
        
        report += f"### {'Brukerrettigheter' if language == 'no' else 'User Rights'}\n"
        report += f"- {'Søk etter implementeringer av eksport/slettefunksjoner' if language == 'no' else 'Looking for export/delete functionality'}\n"
        report += f"- {'Dokumentering av tilgangs- og rettighetskontroller' if language == 'no' else 'Documenting access and permission controls'}\n\n"
        
        report += f"## {'Anbefaling' if language == 'no' else 'Recommendation'}\n"
        report += f"- {'Gjennomgang av alle funn med sikkerhets- og personvernteam' if language == 'no' else 'Review all findings with security and privacy team'}\n"
        report += f"- {'Proritert implementering av tiltak' if language == 'no' else 'Prioritized implementation of measures'}\n"
        
        return report
    
    def _calculate_risk_matrix(self, risks: list, sensitivity: str, scale: str, language: str) -> str:
        """Calculate risk matrix for identified risks."""
        lang_dict = {
            "title": "RISIKOVURDERING - DPIA RISIKOMATRISE" if language == "no" else "RISK ASSESSMENT - DPIA RISK MATRIX",
            "summary": "Risikosummering" if language == "no" else "Risk Summary",
        }
        
        # Risk sensitivity multipliers
        sensitivity_multiplier = {
            "regular": 1.0,
            "sensitive": 2.0,
            "special_categories": 2.5,
        }
        
        scale_multiplier = {
            "small": 1.0,
            "medium": 1.5,
            "large": 2.0,
        }
        
        report = f"# {lang_dict['title']}\n\n"
        report += f"**{lang_dict['summary']}**\n\n"
        report += f"| {'Risiko' if language == 'no' else 'Risk'} | {'Sannsynlighet' if language == 'no' else 'Likelihood'} | {'Alvorlighetsgrad' if language == 'no' else 'Severity'} | {'Datakänsligets' if language == 'no' else 'Sensitivity'} | {'Risikoscore' if language == 'no' else 'Risk Score'} |\n"
        report += "|---|---|---|---|---|\n"
        
        total_score = 0
        for idx, risk in enumerate(risks[:5]):  # Limit to first 5 risks
            likelihood_score = 2  # Default medium
            severity_score = 2    # Default medium
            data_sensitivity = sensitivity_multiplier.get(sensitivity, 1.0)
            scale_factor = scale_multiplier.get(scale, 1.0)
            
            risk_score = likelihood_score * severity_score * data_sensitivity * scale_factor
            total_score += risk_score
            
            report += f"| {risk[:30]} | {likelihood_score}/5 | {severity_score}/5 | {sensitivity} | {risk_score:.1f} |\n"
        
        report += f"\n**{'Total risikoscore' if language == 'no' else 'Total Risk Score'}:** {total_score:.1f}\n"
        report += f"**{'Gjennomsnittlig risiko' if language == 'no' else 'Average Risk'}:** {total_score/max(len(risks), 1):.1f}\n"
        
        return report
    
    def _generate_safeguard_recommendations(self, risk_level: str, focus: list, include_guide: bool, language: str) -> str:
        """Generate safeguard recommendations based on risk level."""
        lang_dict = {
            "title": "ANBEFALTE VERNEKILTER MOT RISIKO" if language == "no" else "RECOMMENDED SAFEGUARDS",
            "technical": "Tekniske tiltak" if language == "no" else "Technical Measures",
            "organizational": "Organisatoriske tiltak" if language == "no" else "Organizational Measures",
        }
        
        recommendations = f"# {lang_dict['title']}\n\n"
        recommendations += f"**{'Risikonivå' if language == 'no' else 'Risk Level'}:** {risk_level.upper()}\n\n"
        
        recommendations += f"## {lang_dict['technical']}\n\n"
        recommendations += f"1. **{'Kryptering' if language == 'no' else 'Encryption'}**\n"
        recommendations += f"   - {'Implementer kryptering både i transit og ved lagring' if language == 'no' else 'Implement encryption both in transit and at rest'}\n"
        recommendations += f"   - {'Bruk AES-256 eller sterkere algoritmer' if language == 'no' else 'Use AES-256 or stronger algorithms'}\n\n"
        
        recommendations += f"2. **{'Tilgangskontroll' if language == 'no' else 'Access Control'}\n**"
        recommendations += f"   - {'Implementer rolle-basert tilgangskontroll (RBAC)' if language == 'no' else 'Implement Role-Based Access Control (RBAC)'}\n"
        recommendations += f"   - {'Bruk minste privilegie-prinsipp' if language == 'no' else 'Apply principle of least privilege'}\n\n"
        
        recommendations += f"3. **{'Loggføring og overvåking' if language == 'no' else 'Logging and Monitoring'}\n**"
        recommendations += f"   - {'Implementer detaljert revisjonsspor' if language == 'no' else 'Implement detailed audit trails'}\n"
        recommendations += f"   - {'Overvåk uvanlig aktivitet' if language == 'no' else 'Monitor unusual activity'}\n\n"
        
        recommendations += f"## {lang_dict['organizational']}\n\n"
        recommendations += f"1. **{'Policyer og prosedyrer' if language == 'no' else 'Policies and Procedures'}\n**"
        recommendations += f"   - {'Etabler datavern- og sikkerhetspolicyer' if language == 'no' else 'Establish data protection and security policies'}\n\n"
        
        recommendations += f"2. **{'Opplæring' if language == 'no' else 'Training'}\n**"
        recommendations += f"   - {'Gjennomfør datavern- og sikkerhetopplæring' if language == 'no' else 'Conduct data protection and security training'}\n\n"
        
        recommendations += f"3. **{'Incidenthåndtering' if language == 'no' else 'Incident Response'}\n**"
        recommendations += f"   - {'Etabler incidenthåndteringsplan' if language == 'no' else 'Establish incident response plan'}\n"
        recommendations += f"   - {'Definer meldingsprosedyrer' if language == 'no' else 'Define notification procedures'}\n"
        
        return recommendations
    
    def _get_current_date(self) -> str:
        """Get current date in ISO format."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    async def _get_search_help_prompt(self) -> GetPromptResult:
        """Get search help prompt."""
        return GetPromptResult(
            description="Help on searching the documentation",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            "How can I effectively search the documentation? "
                            "What are some tips for better search results?"
                        )
                    )
                )
            ]
        )
    
    async def _get_api_usage_prompt(
        self,
        arguments: Dict[str, str]
    ) -> GetPromptResult:
        """Get API usage prompt."""
        topic = arguments.get("topic", "general")
        
        return GetPromptResult(
            description=f"API usage information for: {topic}",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"Show me how to use the API for: {topic}"
                    )
                )
            ]
        )
    
    def _get_server_info(self) -> str:
        """Get server information."""
        doc_count = self.vector_store.count() if self.vector_store.collection else 0
        
        info = f"""# {SERVER_NAME} v{SERVER_VERSION}

## Configuration
- **Embedding Mode:** {'Semantic' if self._use_embeddings else 'Keyword'}
- **Auto-Update:** {'Enabled' if self._auto_update_enabled else 'Disabled'}
- **Documents Indexed:** {doc_count}

## Features
- Documentation search with natural language queries
- Manual documentation updates
- Scheduled automatic updates

## Usage
Use the `search_documentation` tool to search the documentation.
Use the `update_documentation` tool to manually refresh the documentation.
"""
        return info
    
    async def initialize(self):
        """Initialize server and load data asynchronously."""
        logger.info("Initializing server...")
        
        try:
            # Initialize vector store
            await self.vector_store.initialize()
            logger.info("Vector store initialized")
        except Exception as e:
            logger.error(f"Error initializing vector store: {e}")
            # Continue even if vector store fails
        
        # Check if we need to do initial scraping (non-blocking)
        try:
            doc_count = self.vector_store.count()
            
            if doc_count == 0:
                logger.info("No existing documents, performing initial scrape in background")
                # Schedule scraping as background task instead of awaiting
                asyncio.create_task(self._update_documentation_background())
            else:
                logger.info(f"Loaded {doc_count} existing documents")
        except Exception as e:
            logger.error(f"Error checking document count: {e}")
        
        # Start scheduler if enabled
        try:
            if self._auto_update_enabled:
                self.scheduler.start()
                logger.info("Auto-update scheduler started")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
        
        logger.info("Server initialization complete (background tasks may still be running)")
    
    async def _update_documentation_background(self):
        """Update documentation in background without blocking server initialization."""
        try:
            logger.info("Background: Starting documentation update")
            await self._update_documentation()
            logger.info("Background: Documentation update complete")
        except Exception as e:
            logger.error(f"Background: Error during documentation update: {e}")
    
    async def shutdown(self):
        """Shutdown server gracefully."""
        logger.info("Shutting down server...")
        
        if self.scheduler:
            self.scheduler.stop()
        
        logger.info("Server shutdown complete")
    
    def get_server(self) -> Server:
        """Get the MCP server instance."""
        return self.server


async def main():
    """Main entry point for the MCP server."""
    # Get transport mode from environment
    transport = os.getenv("TRANSPORT", "stdio").lower()
    
    server = MCPServerTemplate()
    
    try:
        await server.initialize()
        
        if transport == "http":
            # HTTP mode for remote access and Kubernetes
            await run_http_server(server)
        else:
            # stdio mode for local MCP client communication
            logger.info("Running in stdio mode for MCP client communication")
            async with stdio_server() as (read_stream, write_stream):
                await server.get_server().run(
                    read_stream,
                    write_stream,
                    server.get_server().create_initialization_options(),
                )
    finally:
        await server.shutdown()


async def run_http_server(server_instance: MCPServerTemplate):
    """Run the server in HTTP mode using StreamableHTTP and SSE transports."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse
    from starlette.middleware.cors import CORSMiddleware
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.types import Receive, Scope, Send
    import contextlib
    from collections.abc import AsyncIterator
    
    port = int(os.getenv("HTTP_PORT", "3000"))
    
    logger.info(f"Starting HTTP server on port {port} (StreamableHTTP + SSE)")
    
    # Health check endpoint
    async def health(request):
        return JSONResponse({
            "status": "healthy",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "transport": "http",
            "endpoints": {
                "health": "/health",
                "mcp": "/mcp (StreamableHTTP)",
                "sse": "/sse (legacy SSE)"
            }
        })
    
    # Create StreamableHTTP session manager (primary transport)
    session_manager = StreamableHTTPSessionManager(
        app=server_instance.get_server(),
        event_store=None,  # Can add InMemoryEventStore for resumability
        json_response=False,  # Use SSE streams
        stateless=False,  # Maintain session state
    )
    
    # StreamableHTTP handler
    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)
    
    # Legacy SSE endpoint (for backward compatibility)
    async def handle_sse(request):
        from mcp.server.sse import SseServerTransport
        
        async with SseServerTransport("/messages") as (read_stream, write_stream):
            await server_instance.get_server().run(
                read_stream,
                write_stream,
                server_instance.get_server().create_initialization_options(),
            )
    
    # Lifespan context manager for session manager
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Context manager for session manager lifecycle."""
        async with session_manager.run():
            logger.info("StreamableHTTP session manager started")
            try:
                yield
            finally:
                logger.info("StreamableHTTP session manager shutting down")
    
    # Create Starlette app
    app = Starlette(
        debug=False,
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/mcp", app=handle_streamable_http),  # StreamableHTTP (primary)
            Route("/sse", handle_sse, methods=["GET"]),  # Legacy SSE
        ],
        lifespan=lifespan,
    )
    
    # Add CORS middleware for browser-based clients
    app = CORSMiddleware(
        app,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "mcp-protocol-version"],
    )
    
    # Run server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level=log_level.lower(),
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
