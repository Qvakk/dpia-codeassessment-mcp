"""
Documentation scraper for crawling and extracting content from web pages.
Extended with CSV-based source management and PDF support.
"""

import hashlib
import logging
import os
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .csv_loader import CSVSourceLoader, SourceType
from .pdf_scraper import PDFScraper

logger = logging.getLogger(__name__)


class DocumentationScraper:
    """Scraper for documentation websites."""
    
    def __init__(
        self,
        base_urls: list[str] | None = None,
        swagger_urls: list[str] | None = None,
        max_depth: int = 2,
        max_pages: int = 1000,
        timeout: int = 30,
        use_csv_sources: bool = True,
    ):
        """
        Initialize documentation scraper.
        
        Args:
            base_urls: List of base URLs to scrape (or comma-separated string from env)
            swagger_urls: List of Swagger/OpenAPI JSON URLs (or comma-separated string from env)
            max_depth: Maximum crawl depth
            max_pages: Maximum number of pages to crawl
            timeout: Request timeout in seconds
            use_csv_sources: Load sources from CSV file (default: True)
        """
        # Initialize CSV loader and PDF scraper
        self.csv_loader = CSVSourceLoader() if use_csv_sources else None
        self.pdf_scraper = PDFScraper()
        
        # Initialize state tracking
        self.visited_urls: set[str] = set()
        self.documents: list[dict[str, Any]] = []
        self.timeout = timeout
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        
        # Parse base URLs from env or parameter
        if base_urls is None:
            docs_urls_env = os.getenv("DOCS_URLS", "")
            self.base_urls = [url.strip() for url in docs_urls_env.split(",") if url.strip()]
        else:
            self.base_urls = base_urls if isinstance(base_urls, list) else [base_urls]
        
        # Parse Swagger URLs from env or parameter
        if swagger_urls is None:
            swagger_urls_env = os.getenv("SWAGGER_URLS", "")
            self.swagger_urls = [url.strip() for url in swagger_urls_env.split(",") if url.strip()]
        else:
            self.swagger_urls = swagger_urls if isinstance(swagger_urls, list) else [swagger_urls]
        
        # Store source-specific max_depth mapping
        self.url_max_depth: dict[str, int] = {}
        
        # Load sources from CSV if enabled
        if self.csv_loader:
            logger.info("Loading sources from CSV...")
            sources = self.csv_loader.load_sources()
            
            for source in sources:
                if source.source_type == SourceType.WEB:
                    if source.url not in self.base_urls:
                        self.base_urls.append(source.url)
                    # Store max_depth for this specific URL
                    self.url_max_depth[source.url] = source.max_depth
                # PDFs will be handled separately in scrape()
            
            logger.info(f"Loaded {len(sources)} sources from CSV")
        
        self.max_depth = max_depth or int(os.getenv("CRAWL_MAX_DEPTH", "3"))
        self.max_pages = max_pages or int(os.getenv("CRAWL_MAX_PAGES", "1000"))
    async def scrape(self) -> list[dict[str, Any]]:
        """
        Scrape documentation from all configured URLs (web + PDFs).
        
        Returns:
            List of document dictionaries
        """
        if not self.base_urls and not self.swagger_urls and not self.csv_loader:
            raise ValueError("At least one of DOCS_URLS, SWAGGER_URLS, or CSV sources must be set")
        
        pdf_count = 0
        if self.csv_loader:
            pdf_sources = self.csv_loader.get_pdf_sources()
            pdf_count = len(pdf_sources)
        
        logger.info(
            f"Starting documentation scrape from {len(self.base_urls)} doc URLs, "
            f"{len(self.swagger_urls)} Swagger URLs, and {pdf_count} PDFs"
        )
        self.visited_urls.clear()
        self.documents.clear()
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        ) as client:
            # Scrape regular documentation URLs
            for base_url in self.base_urls:
                # Get source-specific max_depth if available
                url_max_depth = self.url_max_depth.get(base_url, self.max_depth)
                logger.info(f"Scraping documentation from: {base_url} (max_depth={url_max_depth})")
                await self._crawl_url(client, base_url, depth=0, base_url=base_url, max_depth=url_max_depth)
            
            # Scrape Swagger/OpenAPI URLs with specialized parser
            for swagger_url in self.swagger_urls:
                logger.info(f"Scraping Swagger/OpenAPI from: {swagger_url}")
                await self._scrape_swagger(client, swagger_url)
        
        # Scrape PDFs from CSV sources
        if self.csv_loader:
            pdf_sources = self.csv_loader.get_pdf_sources()
            logger.info(f"Scraping {len(pdf_sources)} PDF documents with 10-second timeout per document...")
            
            for source in pdf_sources:
                try:
                    result = self.pdf_scraper.scrape_pdf(
                        source.url,
                        metadata={
                            "name": source.name,
                            "jurisdiction": source.jurisdiction,
                            "language": source.language,
                            "category": source.category,
                            "priority": source.priority.value,
                        },
                        timeout=10  # 10-second timeout per PDF
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
                        self.documents.append(doc)
                        logger.info(f"Successfully scraped PDF: {source.name}")
                
                except Exception as e:
                    logger.error(f"Error scraping PDF {source.name}: {e}")
        
        logger.info(
            f"Scraping complete: {len(self.documents)} documents from "
            f"{len(self.visited_urls)} pages"
        )
        
        return self.documents
    
    async def _crawl_url(
        self,
        client: httpx.AsyncClient,
        url: str,
        depth: int,
        base_url: str,
        max_depth: int | None = None,
    ):
        """
        Crawl a URL and extract documents.
        
        Args:
            client: HTTP client
            url: URL to crawl
            depth: Current crawl depth
            base_url: The base URL for this crawl (to check domain boundaries)
            max_depth: Maximum depth for this specific URL (overrides self.max_depth)
        """
        # Use provided max_depth or fall back to instance default
        effective_max_depth = max_depth if max_depth is not None else self.max_depth
        
        # Check if we should stop
        if depth > effective_max_depth:
            return
        
        if url in self.visited_urls:
            return
        
        if len(self.visited_urls) >= self.max_pages:
            logger.warning(f"Reached max pages limit ({self.max_pages})")
            return
        
        # Mark as visited
        self.visited_urls.add(url)
        
        try:
            # Fetch page
            response = await client.get(url)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, "lxml")
            
            # Extract content
            content = self._extract_content(soup, url)
            
            if content["text"]:
                # Create document
                doc_id = hashlib.md5(url.encode()).hexdigest()
                
                document = {
                    "id": doc_id,
                    "content": content["text"],
                    "title": content["title"],
                    "url": url,
                    "source": "scraper",
                }
                
                self.documents.append(document)
                logger.debug(f"Extracted document from {url} (depth={depth})")
            
            # Find and crawl child links
            if depth < effective_max_depth:
                links = self._extract_links(soup, url, base_url)
                
                for link in links:
                    await self._crawl_url(client, link, depth + 1, base_url, max_depth=effective_max_depth)
        
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching {url}: {e}")
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
    
    def _extract_content(self, soup: BeautifulSoup, url: str) -> dict[str, str]:
        """
        Extract clean content from HTML.
        
        Args:
            soup: BeautifulSoup object
            url: Page URL
        
        Returns:
            Dictionary with title and text
        """
        # Extract title
        title = ""
        if soup.title:
            title = soup.title.string.strip()
        elif soup.h1:
            title = soup.h1.get_text().strip()
        
        # Remove unwanted elements
        for element in soup.find_all([
            "script", "style", "nav", "footer", "header",
            "aside", "form", "iframe", "noscript"
        ]):
            element.decompose()
        
        # Try to find main content area
        main_content = (
            soup.find("main") or
            soup.find("article") or
            soup.find("div", class_=lambda x: x and "content" in x.lower()) or
            soup.find("body")
        )
        
        if not main_content:
            main_content = soup
        
        # Extract text
        text = main_content.get_text(separator="\n", strip=True)
        
        # Clean up text
        lines = [line.strip() for line in text.split("\n")]
        lines = [line for line in lines if line]  # Remove empty lines
        text = "\n".join(lines)
        
        return {
            "title": title,
            "text": text,
        }
    
    def _extract_links(self, soup: BeautifulSoup, base: str, base_url: str) -> list[str]:
        """
        Extract and normalize links from HTML.
        
        Args:
            soup: BeautifulSoup object
            base: Base URL for relative links
            base_url: The base URL for domain checking
        
        Returns:
            List of absolute URLs
        """
        links = []
        base_domain = urlparse(base_url).netloc
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            
            # Skip anchors and special links
            if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
                continue
            
            # Make absolute URL
            absolute_url = urljoin(base, href)
            
            # Only include links from the same domain
            url_domain = urlparse(absolute_url).netloc
            if url_domain != base_domain:
                continue
            
            # Remove fragment
            absolute_url = absolute_url.split("#")[0]
            
            if absolute_url not in self.visited_urls:
                links.append(absolute_url)
        
        return links
    
    def chunk_documents(
        self,
        documents: list[dict[str, Any]],
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Split documents into smaller chunks.
        
        Args:
            documents: List of documents
            chunk_size: Size of each chunk in characters
            chunk_overlap: Overlap between chunks
        
        Returns:
            List of chunked documents
        """
        chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "1000"))
        chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "200"))
        
        chunked_docs = []
        
        for doc in documents:
            content = doc["content"]
            
            if len(content) <= chunk_size:
                # Document fits in one chunk
                chunked_docs.append(doc)
            else:
                # Split into chunks
                chunks = []
                start = 0
                
                while start < len(content):
                    end = start + chunk_size
                    chunk_text = content[start:end]
                    
                    chunk_id = f"{doc['id']}_chunk_{len(chunks)}"
                    chunks.append({
                        "id": chunk_id,
                        "content": chunk_text,
                        "title": doc["title"],
                        "url": doc["url"],
                        "source": doc["source"],
                    })
                    
                    start = end - chunk_overlap
                
                chunked_docs.extend(chunks)
        
        logger.info(
            f"Chunked {len(documents)} documents into {len(chunked_docs)} chunks "
            f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
        )
        
        return chunked_docs
    
    async def _scrape_swagger(self, client: httpx.AsyncClient, swagger_url: str):
        """
        Scrape Swagger/OpenAPI specification.
        
        Args:
            client: HTTP client
            swagger_url: URL to Swagger/OpenAPI JSON
        """
        try:
            logger.info(f"Fetching Swagger/OpenAPI from: {swagger_url}")
            response = await client.get(swagger_url)
            response.raise_for_status()
            
            spec = response.json()
            
            # Extract basic info
            info = spec.get("info", {})
            title = info.get("title", "API Documentation")
            description = info.get("description", "")
            
            # Create a document for the API overview
            if description:
                doc_id = hashlib.md5(swagger_url.encode()).hexdigest()
                self.documents.append({
                    "id": f"{doc_id}_overview",
                    "content": f"{title}\n\n{description}",
                    "title": f"{title} - Overview",
                    "url": swagger_url,
                    "source": "swagger",
                })
            
            # Extract paths and operations
            paths = spec.get("paths", {})
            for path, methods in paths.items():
                for method, operation in methods.items():
                    if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                        continue
                    
                    # Build operation document
                    op_summary = operation.get("summary", "")
                    op_description = operation.get("description", "")
                    op_id = operation.get("operationId", f"{method}_{path}")
                    
                    # Format parameters
                    params = operation.get("parameters", [])
                    params_text = ""
                    if params:
                        params_text = "\n\nParameters:\n"
                        for param in params:
                            param_name = param.get("name", "")
                            param_in = param.get("in", "")
                            param_desc = param.get("description", "")
                            param_required = param.get("required", False)
                            params_text += f"- {param_name} ({param_in}){' [required]' if param_required else ''}: {param_desc}\n"
                    
                    # Format responses
                    responses = operation.get("responses", {})
                    responses_text = ""
                    if responses:
                        responses_text = "\n\nResponses:\n"
                        for code, response in responses.items():
                            response_desc = response.get("description", "")
                            responses_text += f"- {code}: {response_desc}\n"
                    
                    # Create document
                    content = f"{method.upper()} {path}\n\n{op_summary}\n\n{op_description}{params_text}{responses_text}"
                    doc_id = hashlib.md5(f"{swagger_url}_{op_id}".encode()).hexdigest()
                    
                    self.documents.append({
                        "id": doc_id,
                        "content": content.strip(),
                        "title": f"{method.upper()} {path} - {op_summary or op_id}",
                        "url": swagger_url,
                        "source": "swagger",
                    })
            
            logger.info(f"Extracted {len(paths)} API paths from Swagger/OpenAPI")
            
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching Swagger {swagger_url}: {e}")
        except Exception as e:
            logger.error(f"Error parsing Swagger {swagger_url}: {e}")
