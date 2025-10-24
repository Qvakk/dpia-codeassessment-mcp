"""
Input sanitization and validation for MCP security.

Protects against OWASP MCP Top 10 vulnerabilities:
- MCP-01: Prompt Injection
- MCP-08: Data Exfiltration  
- MCP-09: Context Spoofing
"""

import html
import re
import os
from typing import Any, Dict, List
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Sanitizes and validates user inputs to prevent injection attacks."""
    
    MAX_LENGTHS = {
        'query': 5000,
        'url': 2048,
        'filename': 255,
        'text': 50000,
    }
    
    @staticmethod
    def sanitize_prompt(text: str) -> str:
        """
        Sanitize user prompts to prevent injection attacks.
        
        Args:
            text: Raw user input text
            
        Returns:
            Sanitized text safe for processing
        """
        if not text:
            return ""
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # HTML escape to prevent XSS
        text = html.escape(text)
        
        return text
    
    @staticmethod
    def sanitize_query(query: str) -> str:
        """
        Sanitize search queries.
        
        Args:
            query: Search query string
            
        Returns:
            Sanitized query
        """
        if not query:
            return ""
        
        # Limit length
        if len(query) > InputSanitizer.MAX_LENGTHS['query']:
            query = query[:InputSanitizer.MAX_LENGTHS['query']]
        
        # Remove control characters
        query = ''.join(char for char in query if ord(char) >= 32 or char in '\n\t')
        
        # HTML escape
        query = html.escape(query)
        
        return query.strip()
    
    @staticmethod
    def validate_url(url: str, allowed_schemes: List[str] = None) -> bool:
        """
        Validate URL is safe and uses allowed schemes.
        
        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])
            
        Returns:
            True if URL is valid and safe
        """
        if allowed_schemes is None:
            allowed_schemes = ['http', 'https']
        
        if not url or len(url) > InputSanitizer.MAX_LENGTHS['url']:
            return False
        
        try:
            parsed = urlparse(url)
            
            if parsed.scheme not in allowed_schemes:
                logger.warning(f"Invalid URL scheme: {parsed.scheme}")
                return False
            
            # Check for suspicious characters
            if any(char in url for char in ['<', '>', '"', "'", '`']):
                logger.warning(f"Suspicious characters in URL")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"URL validation error: {e}")
            return False
    
    @staticmethod
    def sanitize_path(file_path: str, allowed_dirs: List[str] = None) -> str:
        """
        Sanitize and validate file path to prevent path traversal attacks.
        
        Args:
            file_path: File path to sanitize
            allowed_dirs: List of allowed directory paths
            
        Returns:
            Sanitized and validated path
            
        Raises:
            ValueError: If path is invalid or unsafe
        """
        if not file_path:
            raise ValueError("File path cannot be empty")
        
        # Remove null bytes
        file_path = file_path.replace('\x00', '')
        
        # Normalize path separators
        file_path = os.path.normpath(file_path)
        
        # Check for path traversal patterns
        if '..' in file_path:
            logger.warning(f"Path traversal attempt detected: {file_path}")
            raise ValueError("Path traversal not allowed")
        
        # Get absolute path and check it's within allowed directories
        try:
            abs_path = os.path.abspath(file_path)
            
            if allowed_dirs:
                allowed = any(
                    abs_path.startswith(os.path.abspath(allowed_dir))
                    for allowed_dir in allowed_dirs
                )
                
                if not allowed:
                    logger.warning(f"File path outside allowed directories")
                    raise ValueError("File path outside allowed directories")
            
            return abs_path
            
        except Exception as e:
            logger.error(f"File path sanitization error: {e}")
            raise ValueError(f"Invalid file path: {e}")
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_dirs: List[str] = None) -> bool:
        """
        Validate file path to prevent path traversal attacks.
        
        Args:
            file_path: File path to validate
            allowed_dirs: List of allowed directory paths
            
        Returns:
            True if path is safe
        """
        if not file_path:
            return False
        
        # Check for path traversal patterns
        if '..' in file_path or file_path.startswith('/'):
            logger.warning(f"Path traversal attempt detected: {file_path}")
            return False
        
        # Get absolute path and check it's within allowed directories
        try:
            abs_path = os.path.abspath(file_path)
            
            if allowed_dirs:
                allowed = any(
                    abs_path.startswith(os.path.abspath(allowed_dir))
                    for allowed_dir in allowed_dirs
                )
                
                if not allowed:
                    logger.warning(f"File path outside allowed directories")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"File path validation error: {e}")
            return False
    
    @staticmethod
    def sanitize_output(data: Any) -> Any:
        """
        Sanitize output data to prevent sensitive data leakage.
        
        Args:
            data: Data to sanitize
            
        Returns:
            Sanitized data
        """
        # Patterns for sensitive data
        redact_patterns = [
            (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})(["\']?)', r'\1***REDACTED***\3'),
            (r'(token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})(["\']?)', r'\1***REDACTED***\3'),
            (r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]{8,})(["\']?)', r'\1***REDACTED***\3'),
        ]
        
        if isinstance(data, str):
            for pattern, replacement in redact_patterns:
                data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
            return data
        
        elif isinstance(data, dict):
            return {key: InputSanitizer.sanitize_output(value) 
                   for key, value in data.items()}
        
        elif isinstance(data, list):
            return [InputSanitizer.sanitize_output(item) for item in data]
        
        return data


def sanitize_tool_arguments(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize tool arguments before execution.
    
    Args:
        arguments: Tool arguments from MCP client
        
    Returns:
        Sanitized arguments
    """
    sanitized = {}
    
    for key, value in arguments.items():
        if isinstance(value, str):
            # Sanitize string inputs
            if 'url' in key.lower():
                if InputSanitizer.validate_url(value):
                    sanitized[key] = value
                else:
                    logger.error(f"Invalid URL in argument {key}")
                    sanitized[key] = ""
            elif 'path' in key.lower() or 'file' in key.lower():
                if InputSanitizer.validate_file_path(value):
                    sanitized[key] = value
                else:
                    logger.error(f"Invalid file path in argument {key}")
                    sanitized[key] = ""
            else:
                sanitized[key] = InputSanitizer.sanitize_query(value)
        else:
            sanitized[key] = value
    
    return sanitized
