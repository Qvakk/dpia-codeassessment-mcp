"""
PDF scraper for legal documents.
Downloads and extracts text from PDF files.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Suppress pypdf encoding warnings that cause server hangs
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._cmap").setLevel(logging.CRITICAL)


class PDFScraper:
    """Scrape and extract text from PDF documents."""
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize PDF scraper.
        
        Args:
            cache_dir: Directory to cache downloaded PDFs
        """
        if cache_dir is None:
            cache_dir = os.getenv("PDF_CACHE_DIR", "data/pdf_cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for PDF libraries
        self.pdf_backend = self._detect_pdf_backend()
        logger.info(f"PDF scraper initialized with backend: {self.pdf_backend}")
    
    def _detect_pdf_backend(self) -> str:
        """Detect available PDF extraction library."""
        try:
            import pypdf
            return "pypdf"
        except ImportError:
            pass
        
        try:
            import pdfplumber
            return "pdfplumber"
        except ImportError:
            pass
        
        try:
            import PyPDF2
            return "pypdf2"
        except ImportError:
            pass
        
        logger.warning("No PDF library found. Install: pip install pypdf or pdfplumber")
        return "none"
    
    def download_pdf(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        Download PDF from URL.
        
        Args:
            url: URL to PDF file
            filename: Optional filename to save as
        
        Returns:
            Path to downloaded file or None on error
        """
        try:
            # Generate filename from URL if not provided
            if filename is None:
                parsed = urlparse(url)
                filename = Path(parsed.path).name
                if not filename.endswith('.pdf'):
                    filename = f"{filename}.pdf"
            
            filepath = self.cache_dir / filename
            
            # Check if already cached
            if filepath.exists():
                logger.info(f"Using cached PDF: {filepath}")
                return filepath
            
            # Download
            logger.info(f"Downloading PDF: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Save to cache
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"PDF downloaded: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error downloading PDF from {url}: {e}")
            return None
    
    def extract_text_pypdf(self, pdf_path: Path, timeout: int = 10) -> str:
        """Extract text using pypdf library with timeout and error handling."""
        import pypdf
        
        text_parts = []
        try:
            with open(pdf_path, 'rb') as f:
                reader = pypdf.PdfReader(f)
                
                # Skip if too many pages (likely scanned/image PDFs)
                if len(reader.pages) > 500:
                    logger.warning(f"PDF has {len(reader.pages)} pages, likely image-based. Skipping.")
                    return "[PDF with too many pages - likely scanned document]"
                
                for page_num, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():  # Only add non-empty text
                            text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")
                    except Exception as e:
                        logger.debug(f"Error extracting page {page_num + 1}: {e}")
                
        except Exception as e:
            logger.error(f"Error with pypdf extraction: {e}")
            return "[PDF extraction failed]"
        
        return "\n".join(text_parts) if text_parts else "[PDF extracted but contains no text]"
    
    def extract_text_pdfplumber(self, pdf_path: Path) -> str:
        """Extract text using pdfplumber library."""
        import pdfplumber
        
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num + 1}: {e}")
        
        return "\n".join(text_parts)
    
    def extract_text_pypdf2(self, pdf_path: Path) -> str:
        """Extract text using PyPDF2 library."""
        import PyPDF2
        
        text_parts = []
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page_num in range(len(reader.pages)):
                try:
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text_parts.append(f"\n--- Page {page_num + 1} ---\n{text}")
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num + 1}: {e}")
        
        return "\n".join(text_parts)
    
    def extract_text(self, pdf_path: Path, timeout: int = 10) -> Optional[str]:
        """
        Extract text from PDF file with timeout protection.
        
        Args:
            pdf_path: Path to PDF file
            timeout: Timeout in seconds for extraction
        
        Returns:
            Extracted text or None on error
        """
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return None
        
        try:
            if self.pdf_backend == "pypdf":
                return self.extract_text_pypdf(pdf_path, timeout=timeout)
            elif self.pdf_backend == "pdfplumber":
                return self.extract_text_pdfplumber(pdf_path)
            elif self.pdf_backend == "pypdf2":
                return self.extract_text_pypdf2(pdf_path)
            else:
                logger.error("No PDF extraction backend available")
                return None
        
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return None
    
    def scrape_pdf(self, url: str, metadata: Optional[Dict] = None, timeout: int = 10) -> Optional[Dict]:
        """
        Download and extract text from PDF URL with timeout and error handling.
        
        Args:
            url: URL to PDF file
            metadata: Optional metadata to include
            timeout: Timeout in seconds for PDF extraction
        
        Returns:
            Dictionary with extracted content and metadata, or None on error
        """
        try:
            # Download PDF
            pdf_path = self.download_pdf(url)
            if pdf_path is None:
                return None
            
            # Extract text with timeout
            text = self.extract_text(pdf_path, timeout=timeout)
            if text is None:
                return None
            
            # Build result
            result = {
                "url": url,
                "text": text,
                "source_type": "pdf",
                "file_path": str(pdf_path),
            }
            
            if metadata:
                result.update(metadata)
            
            return result
        
        except Exception as e:
            logger.error(f"Error scraping PDF {url}: {e}")
            return None
    
    def scrape_multiple_pdfs(self, urls: List[str]) -> List[Dict]:
        """
        Scrape multiple PDFs.
        
        Args:
            urls: List of PDF URLs
        
        Returns:
            List of extracted content dictionaries
        """
        results = []
        for url in urls:
            logger.info(f"Scraping PDF: {url}")
            result = self.scrape_pdf(url)
            if result:
                results.append(result)
        
        logger.info(f"Successfully scraped {len(results)}/{len(urls)} PDFs")
        return results


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scraper = PDFScraper()
    
    # Test with a sample PDF
    test_url = "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32016R0679"
    
    result = scraper.scrape_pdf(
        test_url,
        metadata={
            "name": "GDPR Official Text",
            "jurisdiction": "EU",
            "language": "en"
        }
    )
    
    if result:
        print(f"\nSuccessfully extracted {len(result['text'])} characters")
        print(f"First 500 characters:\n{result['text'][:500]}...")
