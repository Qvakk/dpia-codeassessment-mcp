"""
Embedding service with support for multiple providers:
- HuggingFace (local, sentence-transformers)
- OpenAI (API-based)
- Azure OpenAI (API-based)
"""

import logging
import os
from typing import List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    AZURE = "azure"


class EmbeddingService:
    """Unified embedding service supporting multiple providers."""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        """
        Initialize embedding service.
        
        Args:
            provider: Embedding provider (huggingface, openai, azure)
            model: Model name/identifier
            dimension: Embedding dimension
        """
        self.provider = EmbeddingProvider(
            provider or os.getenv("EMBEDDING_PROVIDER", "huggingface")
        )
        self.dimension = dimension or int(os.getenv("EMBEDDING_DIMENSION", "384"))
        
        # Initialize based on provider
        if self.provider == EmbeddingProvider.HUGGINGFACE:
            self._init_huggingface(model)
        elif self.provider == EmbeddingProvider.OPENAI:
            self._init_openai(model)
        elif self.provider == EmbeddingProvider.AZURE:
            self._init_azure(model)
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")
        
        logger.info(
            f"Initialized {self.provider} embedding service with dimension {self.dimension}"
        )
    
    def _init_huggingface(self, model: Optional[str] = None):
        """Initialize HuggingFace sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer
            
            self.model_name = model or os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2"
            )
            
            logger.info(f"Loading HuggingFace model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.tokenizer = self.model.tokenizer if hasattr(self.model, 'tokenizer') else None
            
            # Get actual dimension from model
            self.dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info(f"HuggingFace model loaded successfully (dim={self.dimension})")
            
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
    
    def _init_openai(self, model: Optional[str] = None):
        """Initialize OpenAI embeddings."""
        try:
            from openai import OpenAI
            import tiktoken
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            
            self.client = OpenAI(api_key=api_key)
            self.model_name = model or os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small"
            )
            
            # Initialize tokenizer for token counting
            try:
                self.tokenizer = tiktoken.encoding_for_model(self.model_name)
            except KeyError:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
            
            logger.info(f"OpenAI embedding service initialized: {self.model_name}")
            
        except ImportError:
            raise ImportError(
                "openai not installed. Install with: pip install openai tiktoken"
            )
    
    def _init_azure(self, model: Optional[str] = None):
        """Initialize Azure OpenAI embeddings."""
        try:
            from openai import AzureOpenAI
            import tiktoken
            
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            
            if not api_key or not endpoint:
                raise ValueError(
                    "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set"
                )
            
            self.client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
            )
            
            self.model_name = model or os.getenv(
                "AZURE_OPENAI_DEPLOYMENT_NAME",
                "text-embedding-ada-002"
            )
            
            # Initialize tokenizer
            try:
                self.tokenizer = tiktoken.encoding_for_model("text-embedding-ada-002")
            except KeyError:
                self.tokenizer = tiktoken.get_encoding("cl100k_base")
            
            logger.info(
                f"Azure OpenAI embedding service initialized: {self.model_name}"
            )
            
        except ImportError:
            raise ImportError(
                "openai not installed. Install with: pip install openai tiktoken"
            )
    
    def encode(self, texts: List[str], show_progress: bool = False) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            show_progress: Show progress bar (HuggingFace only)
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        if self.provider == EmbeddingProvider.HUGGINGFACE:
            return self._encode_huggingface(texts, show_progress)
        elif self.provider == EmbeddingProvider.OPENAI:
            return self._encode_openai(texts)
        elif self.provider == EmbeddingProvider.AZURE:
            return self._encode_azure(texts)
    
    def _encode_huggingface(
        self,
        texts: List[str],
        show_progress: bool = False
    ) -> List[List[float]]:
        """Encode using HuggingFace model."""
        # Truncate texts to max token length
        max_length = self.model.max_seq_length
        truncated_texts = []
        
        for text in texts:
            if self.tokenizer:
                tokens = self.tokenizer.encode(text, truncation=True, max_length=max_length)
                truncated_text = self.tokenizer.decode(tokens, skip_special_tokens=True)
                truncated_texts.append(truncated_text)
            else:
                # Fallback: simple character truncation
                truncated_texts.append(text[:max_length * 4])
        
        embeddings = self.model.encode(
            truncated_texts,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )
        
        return embeddings.tolist()
    
    def _encode_openai(self, texts: List[str]) -> List[List[float]]:
        """Encode using OpenAI API."""
        embeddings = []
        
        # Process in batches to respect API limits
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Truncate texts that are too long
            truncated_batch = [self._truncate_text_openai(text) for text in batch]
            
            response = self.client.embeddings.create(
                model=self.model_name,
                input=truncated_batch,
            )
            
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    def _encode_azure(self, texts: List[str]) -> List[List[float]]:
        """Encode using Azure OpenAI API."""
        embeddings = []
        
        # Process in batches
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            # Truncate texts that are too long
            truncated_batch = [self._truncate_text_openai(text) for text in batch]
            
            response = self.client.embeddings.create(
                model=self.model_name,
                input=truncated_batch,
            )
            
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        
        return embeddings
    
    def _truncate_text_openai(self, text: str, max_tokens: int = 8191) -> str:
        """Truncate text to fit within token limit for OpenAI models."""
        tokens = self.tokenizer.encode(text)
        
        if len(tokens) <= max_tokens:
            return text
        
        # Truncate and decode
        truncated_tokens = tokens[:max_tokens]
        return self.tokenizer.decode(truncated_tokens)
    
    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.dimension
