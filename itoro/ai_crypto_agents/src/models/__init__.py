"""
🌙 Anarcho Capital's Model System
Built with love by Anarcho Capital 🚀
"""

from .base_model import BaseModel, ModelResponse
from .claude_model import ClaudeModel
from .groq_model import GroqModel
from .openai_model import OpenAIModel
from .deepseek_model import DeepSeekModel
from .model_factory import model_factory

# Optional imports for models that may have missing dependencies
try:
    from .gemini_model import GeminiModel
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GeminiModel = None

__all__ = [
    'BaseModel',
    'ModelResponse',
    'ClaudeModel',
    'GroqModel',
    'OpenAIModel',
    'DeepSeekModel',
    'model_factory'
]

if GEMINI_AVAILABLE:
    __all__.append('GeminiModel') 