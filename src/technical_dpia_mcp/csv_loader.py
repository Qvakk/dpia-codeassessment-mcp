"""
CSV-based loader for legal documents and web pages.
Manages scraping PDFs and URLs into the vector database.
"""

import csv
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Type of source to scrape."""
    PDF = "pdf"
    WEB = "web"


class Priority(Enum):
    """Priority level for source updates."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class LegalSource:
    """Represents a legal document source."""
    source_type: SourceType
    name: str
    url: str
    language: str
    jurisdiction: str
    category: str
    priority: Priority
    update_frequency: str
    max_depth: int = 2
    
    @classmethod
    def from_csv_row(cls, row: dict) -> "LegalSource":
        """Create LegalSource from CSV row."""
        return cls(
            source_type=SourceType(row["source_type"].lower()),
            name=row["name"],
            url=row["url"],
            language=row["language"],
            jurisdiction=row["jurisdiction"],
            category=row["category"],
            priority=Priority(row["priority"].lower()),
            update_frequency=row["update_frequency"],
            max_depth=int(row.get("max_depth", 2)),
        )


class CSVSourceLoader:
    """Load and manage legal sources from CSV file."""
    
    def __init__(self, csv_path: Optional[str] = None):
        """
        Initialize CSV loader.
        
        Args:
            csv_path: Path to CSV file. If None, uses DATA_SOURCES_CSV env var
                     or defaults to data/legal_sources.csv
        """
        if csv_path is None:
            csv_path = os.getenv(
                "DATA_SOURCES_CSV",
                "data/legal_sources.csv"
            )
        
        self.csv_path = Path(csv_path)
        if not self.csv_path.is_absolute():
            # Make relative to project root
            project_root = Path(__file__).parent.parent.parent
            self.csv_path = project_root / self.csv_path
        
        logger.info(f"CSV source loader initialized with: {self.csv_path}")
    
    def load_sources(self, 
                     filter_priority: Optional[List[Priority]] = None,
                     filter_jurisdiction: Optional[List[str]] = None,
                     filter_type: Optional[List[SourceType]] = None) -> List[LegalSource]:
        """
        Load sources from CSV with optional filtering.
        
        Args:
            filter_priority: Only load sources with these priorities
            filter_jurisdiction: Only load sources from these jurisdictions
            filter_type: Only load these source types (pdf, web)
        
        Returns:
            List of LegalSource objects
        """
        if not self.csv_path.exists():
            logger.error(f"CSV file not found: {self.csv_path}")
            return []
        
        sources = []
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Skip empty rows
                    if not row.get('url'):
                        continue
                    
                    try:
                        source = LegalSource.from_csv_row(row)
                        
                        # Apply filters
                        if filter_priority and source.priority not in filter_priority:
                            continue
                        
                        if filter_jurisdiction and source.jurisdiction not in filter_jurisdiction:
                            continue
                        
                        if filter_type and source.source_type not in filter_type:
                            continue
                        
                        sources.append(source)
                        logger.debug(f"Loaded source: {source.name}")
                    
                    except Exception as e:
                        logger.error(f"Error parsing row {row}: {e}")
                        continue
            
            logger.info(f"Loaded {len(sources)} sources from CSV")
            return sources
        
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            return []
    
    def get_urls(self, **filters) -> List[str]:
        """
        Get list of URLs from sources.
        
        Args:
            **filters: Passed to load_sources()
        
        Returns:
            List of URLs
        """
        sources = self.load_sources(**filters)
        return [source.url for source in sources]
    
    def get_sources_by_priority(self, priority: Priority) -> List[LegalSource]:
        """Get all sources with specific priority."""
        return self.load_sources(filter_priority=[priority])
    
    def get_sources_by_jurisdiction(self, jurisdiction: str) -> List[LegalSource]:
        """Get all sources for specific jurisdiction."""
        return self.load_sources(filter_jurisdiction=[jurisdiction])
    
    def get_pdf_sources(self) -> List[LegalSource]:
        """Get all PDF sources."""
        return self.load_sources(filter_type=[SourceType.PDF])
    
    def get_web_sources(self) -> List[LegalSource]:
        """Get all web sources."""
        return self.load_sources(filter_type=[SourceType.WEB])


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    loader = CSVSourceLoader()
    
    # Load all sources
    all_sources = loader.load_sources()
    print(f"\nTotal sources: {len(all_sources)}")
    
    # Load high priority sources
    high_priority = loader.get_sources_by_priority(Priority.HIGH)
    print(f"\nHigh priority sources: {len(high_priority)}")
    for source in high_priority:
        print(f"  - {source.name} ({source.source_type.value})")
    
    # Load Norwegian sources
    no_sources = loader.get_sources_by_jurisdiction("NO")
    print(f"\nNorwegian sources: {len(no_sources)}")
    for source in no_sources:
        print(f"  - {source.name}")
    
    # Get all PDF URLs
    pdf_urls = loader.get_urls(filter_type=[SourceType.PDF])
    print(f"\nPDF URLs: {len(pdf_urls)}")
    for url in pdf_urls:
        print(f"  - {url}")
