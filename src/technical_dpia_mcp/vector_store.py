"""
Vector store using ChromaDB with dual search modes:
- Semantic search (using embeddings)
- Keyword search (text matching)
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional
from collections import defaultdict

import chromadb
from chromadb.config import Settings
from chromadb.errors import NotFoundError

from .embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for document storage and retrieval using ChromaDB."""
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        use_embeddings: bool = True,
    ):
        """
        Initialize vector store.
        
        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the ChromaDB collection
            use_embeddings: Whether to use embeddings for search
        """
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY",
            "./data/chroma_db"
        )
        self.collection_name = collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME",
            "documentation"
        )
        self.use_embeddings = use_embeddings
        self.embedding_service: Optional[EmbeddingService] = None
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None
        
        logger.info(
            f"VectorStore initialized (embeddings={'enabled' if use_embeddings else 'disabled'})"
        )
    
    async def initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Create ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                )
            )
            
            # Initialize embedding service if needed
            if self.use_embeddings:
                self.embedding_service = EmbeddingService()
                embedding_dimension = self.embedding_service.get_dimension()
            else:
                embedding_dimension = 384  # Default dimension for dummy embeddings
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                )
                logger.info(
                    f"Loaded existing collection '{self.collection_name}' "
                    f"with {self.collection.count()} documents"
                )
            except (ValueError, NotFoundError):
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"Created new collection '{self.collection_name}'")
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    async def add_documents(
        self,
        documents: List[Dict[str, Any]],
        show_progress: bool = False,
    ):
        """
        Add documents to the vector store.
        
        Args:
            documents: List of document dictionaries with 'content', 'title', 'url', etc.
            show_progress: Show progress during embedding generation
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        logger.info(f"Adding {len(documents)} documents to vector store")
        start_time = time.time()
        
        # Prepare data
        ids = [doc["id"] for doc in documents]
        texts = [doc["content"] for doc in documents]
        metadatas = [
            {
                "title": doc.get("title", ""),
                "url": doc.get("url", ""),
                "source": doc.get("source", ""),
            }
            for doc in documents
        ]
        
        # Generate embeddings
        if self.use_embeddings and self.embedding_service:
            logger.info("Generating embeddings...")
            embeddings = self.embedding_service.encode(texts, show_progress=show_progress)
        else:
            # Use dummy embeddings for keyword-only mode
            embedding_dim = 384
            embeddings = [[0.0] * embedding_dim for _ in texts]
        
        # Add to collection
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        
        elapsed = time.time() - start_time
        logger.info(
            f"Added {len(documents)} documents in {elapsed:.2f}s "
            f"({len(documents)/elapsed:.1f} docs/sec)"
        )
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        use_embeddings: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for documents.
        
        Args:
            query: Search query
            limit: Maximum number of results
            use_embeddings: Override default embedding usage
        
        Returns:
            List of matching documents with scores
        """
        use_emb = use_embeddings if use_embeddings is not None else self.use_embeddings
        
        if use_emb and self.embedding_service:
            return await self._search_semantic(query, limit)
        else:
            return await self._search_keyword(query, limit)
    
    async def _search_semantic(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform semantic search using embeddings."""
        start_time = time.time()
        
        # Generate query embedding
        query_embedding = self.embedding_service.encode([query])[0]
        
        # Search collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
        )
        
        # Format results
        documents = []
        for i in range(len(results["ids"][0])):
            documents.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "title": results["metadatas"][0][i].get("title", ""),
                "url": results["metadatas"][0][i].get("url", ""),
                "score": 1.0 - results["distances"][0][i],  # Convert distance to similarity
            })
        
        elapsed = time.time() - start_time
        logger.info(
            f"Semantic search completed in {elapsed:.3f}s, found {len(documents)} results"
        )
        
        return documents
    
    async def _search_keyword(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Perform keyword-based search."""
        start_time = time.time()
        
        # Get all documents
        all_docs = self.collection.get(
            include=["documents", "metadatas"]
        )
        
        # Score documents
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        scored_docs = []
        for i, (doc_id, content, metadata) in enumerate(
            zip(all_docs["ids"], all_docs["documents"], all_docs["metadatas"])
        ):
            content_lower = content.lower()
            title_lower = metadata.get("title", "").lower()
            
            # Calculate score
            score = 0.0
            
            # Exact phrase match (highest weight)
            if query_lower in content_lower:
                score += 3.0
            if query_lower in title_lower:
                score += 5.0
            
            # Individual term matches
            content_terms = set(content_lower.split())
            title_terms = set(title_lower.split())
            
            matching_terms = query_terms & content_terms
            score += len(matching_terms) * 0.5
            
            matching_title_terms = query_terms & title_terms
            score += len(matching_title_terms) * 2.0
            
            if score > 0:
                scored_docs.append({
                    "id": doc_id,
                    "content": content,
                    "title": metadata.get("title", ""),
                    "url": metadata.get("url", ""),
                    "score": score,
                })
        
        # Sort by score and limit results
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        results = scored_docs[:limit]
        
        elapsed = time.time() - start_time
        logger.info(
            f"Keyword search completed in {elapsed:.3f}s, found {len(results)} results"
        )
        
        return results
    
    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID."""
        try:
            result = self.collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "content": result["documents"][0],
                    "title": result["metadatas"][0].get("title", ""),
                    "url": result["metadatas"][0].get("url", ""),
                }
        except Exception as e:
            logger.error(f"Error retrieving document {doc_id}: {e}")
        
        return None
    
    async def delete_all(self):
        """Delete all documents from the collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("All documents deleted from collection")
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise
    
    def count(self) -> int:
        """Get the total number of documents in the collection."""
        return self.collection.count()
