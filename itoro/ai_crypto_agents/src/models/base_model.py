"""
🌙 Anarcho Capital's Model Interface
Built with love by Anarcho Capital 🚀

This module defines the base interface for all AI models.
"""

from abc import ABC, abstractmethod
import sys
from typing import Dict, List, Optional, Any, TypeVar, Union
from dataclasses import dataclass

# Handle Self type annotation in a version-compatible way
if sys.version_info >= (3, 11):
    from typing import Self
else:
    # For older Python versions, use TypeVar as a substitute for Self
    Self = TypeVar('Self', bound='BaseModel')

@dataclass
class ModelResponse:
    """Standardized response format for all models"""
    content: str
    raw_response: Any  # Original response object
    model_name: str
    usage: Optional[Dict] = None
    
class BaseModel(ABC):
    """Base interface for all AI models"""
    
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self.client = None
        self.initialize_client(**kwargs)
    
    @abstractmethod
    def initialize_client(self, **kwargs) -> None:
        """Initialize the model's client"""
        pass
    
    @abstractmethod
    def generate_response(self, 
        system_prompt: str,
        user_content: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> ModelResponse:
        """Generate a response from the model"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the model is available and properly configured"""
        pass
    
    @property
    @abstractmethod
    def model_type(self) -> str:
        """Return the type/name of the model"""
        pass 