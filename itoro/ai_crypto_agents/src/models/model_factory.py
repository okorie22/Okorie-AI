"""
🌙 Anarcho Capital's Model Factory
Built with love by Anarcho Capital 🚀

This module manages all available AI models and provides a unified interface.
"""

import os
from typing import Dict, Optional, Type
from termcolor import cprint
from dotenv import load_dotenv
from pathlib import Path
from .base_model import BaseModel
from .claude_model import ClaudeModel
from .groq_model import GroqModel
from .openai_model import OpenAIModel
from .deepseek_model import DeepSeekModel

# Optional imports for models that may have missing dependencies
try:
    from .gemini_model import GeminiModel
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    GeminiModel = None

# Import config for quiet mode
try:
    from src.config import MODEL_FACTORY_QUIET_MODE, SHOW_DEBUG_IN_CONSOLE, LOG_LEVEL
except ImportError:
    # Fallback if config not available
    MODEL_FACTORY_QUIET_MODE = True
    SHOW_DEBUG_IN_CONSOLE = False
    LOG_LEVEL = "INFO"

class ModelFactory:
    """Factory for creating and managing AI models"""
    
    # Map model types to their implementations
    MODEL_IMPLEMENTATIONS = {
        "claude": ClaudeModel,
        "groq": GroqModel,
        "openai": OpenAIModel,
        "deepseek": DeepSeekModel
    }
    
    # Add Gemini only if available
    if GEMINI_AVAILABLE:
        MODEL_IMPLEMENTATIONS["gemini"] = GeminiModel
    
    # Default models for each type
    DEFAULT_MODELS = {
        "claude": "claude-3-5-haiku-latest",  # Latest fast Claude model
        "groq": "mixtral-8x7b-32768",        # Fast Mixtral model
        "openai": "gpt-4o",                  # Latest GPT-4 Optimized
        "gemini": "gemini-2.0-flash-exp",    # Latest Gemini model
        "deepseek": "deepseek-chat"          # Fast chat model
    }
    
    def __init__(self, quiet_mode: bool = None):
        # Determine quiet mode - use parameter, then config, then fallback
        if quiet_mode is None:
            self.quiet_mode = MODEL_FACTORY_QUIET_MODE or (not SHOW_DEBUG_IN_CONSOLE and LOG_LEVEL != "DEBUG")
        else:
            self.quiet_mode = quiet_mode
        
        if not self.quiet_mode:
            self._log("\n🏗️ Creating new ModelFactory instance...", "cyan")
        
        # Load environment variables first
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / '.env'
        self._log(f"\n🔍 Loading environment from: {env_path}", "cyan")
        load_dotenv(dotenv_path=env_path)
        self._log("✨ Environment loaded", "green")
        
        self._models: Dict[str, BaseModel] = {}
        self._initialize_models()
    
    def _log(self, message: str, color: str = "white"):
        """Log message only if not in quiet mode"""
        if not self.quiet_mode:
            self._log(message, color)
    
    def _initialize_models(self):
        """Initialize all available models"""
        initialized = False
        
        self._log("\n🏭 Anarcho Capital's Model Factory Initialization", "cyan")
        self._log("═" * 50, "cyan")
        
        # Debug current environment without exposing values
        self._log("\n🔍 Environment Check:", "cyan")
        for key in ["GROQ_API_KEY", "OPENAI_KEY", "ANTHROPIC_KEY", "GEMINI_KEY", "DEEPSEEK_KEY"]:
            value = os.getenv(key)
            if value and len(value.strip()) > 0:
                self._log(f"  ├─ {key}: Found ({len(value)} chars)", "green")
            else:
                self._log(f"  ├─ {key}: Not found or empty", "red")
        
        # Try to initialize each model type
        for model_type, key_name in self._get_api_key_mapping().items():
            self._log(f"\n🔄 Initializing {model_type} model...", "cyan")
            self._log(f"  ├─ Looking for {key_name}...", "cyan")
            
            if api_key := os.getenv(key_name):
                try:
                    self._log(f"  ├─ Found {key_name} ({len(api_key)} chars)", "green")
                    self._log(f"  ├─ Getting model class for {model_type}...", "cyan")
                    
                    if model_type not in self.MODEL_IMPLEMENTATIONS:
                        self._log(f"  ├─ ❌ Model type not found in implementations!", "red")
                        self._log(f"  └─ Available implementations: {list(self.MODEL_IMPLEMENTATIONS.keys())}", "yellow")
                        continue
                    
                    model_class = self.MODEL_IMPLEMENTATIONS[model_type]
                    self._log(f"  ├─ Using model class: {model_class.__name__}", "cyan")
                    self._log(f"  ├─ Model class methods: {dir(model_class)}", "cyan")
                    
                    # Create instance with more detailed error handling
                    try:
                        self._log(f"  ├─ Creating model instance...", "cyan")
                        self._log(f"  ├─ Default model name: {self.DEFAULT_MODELS[model_type]}", "cyan")
                        model_instance = model_class(api_key)
                        self._log(f"  ├─ Model instance created", "green")
                        
                        # Test if instance is properly initialized
                        self._log(f"  ├─ Testing model availability...", "cyan")
                        if model_instance.is_available():
                            self._models[model_type] = model_instance
                            initialized = True
                            self._log(f"  └─ ✨ Successfully initialized {model_type}", "green")
                        else:
                            self._log(f"  └─ ⚠️ Model instance created but not available", "yellow")
                            self._log(f"  └─ Client status: {model_instance.client}", "yellow")
                    except Exception as instance_error:
                        self._log(f"  ├─ ⚠️ Error creating model instance", "yellow")
                        self._log(f"  ├─ Error type: {type(instance_error).__name__}", "yellow")
                        self._log(f"  ├─ Error message: {str(instance_error)}", "yellow")
                        if hasattr(instance_error, '__traceback__'):
                            import traceback
                            self._log(f"  └─ Traceback:\n{traceback.format_exc()}", "yellow")
                        
                except Exception as e:
                    self._log(f"  ├─ ⚠️ Failed to initialize {model_type} model", "yellow")
                    self._log(f"  ├─ Error type: {type(e).__name__}", "yellow")
                    self._log(f"  ├─ Error message: {str(e)}", "yellow")
                    if hasattr(e, '__traceback__'):
                        import traceback
                        self._log(f"  └─ Traceback:\n{traceback.format_exc()}", "yellow")
            else:
                self._log(f"  └─ ℹ️ {key_name} not found", "blue")
        
        self._log("\n" + "═" * 50, "cyan")
        self._log(f"📊 Initialization Summary:", "cyan")
        self._log(f"  ├─ Models attempted: {len(self._get_api_key_mapping())}", "cyan")
        self._log(f"  ├─ Models initialized: {len(self._models)}", "cyan")
        self._log(f"  └─ Available models: {list(self._models.keys())}", "cyan")
        
        if not initialized:
            self._log("\n⚠️ No AI models available - check API keys", "yellow")
            self._log("Required environment variables:", "yellow")
            for model_type, key_name in self._get_api_key_mapping().items():
                self._log(f"  ├─ {key_name} (for {model_type})", "yellow")
            self._log("  └─ Add these to your .env file 🌙", "yellow")
        else:
            # Print available models
            self._log("\n🤖 Available AI Models:", "cyan")
            for model_type, model in self._models.items():
                self._log(f"  ├─ {model_type}: {model.model_name}", "green")
            self._log("  └─ Anarcho Capital's Model Factory Ready! 🌙", "green")
    
    def get_model(self, model_type: str, model_name: Optional[str] = None) -> Optional[BaseModel]:
        """Get a specific model instance"""
        self._log(f"\n🔍 Requesting model: {model_type} ({model_name or 'default'})", "cyan")
        
        if model_type not in self.MODEL_IMPLEMENTATIONS:
            self._log(f"❌ Invalid model type: '{model_type}'", "red")
            self._log("Available types:", "yellow")
            for available_type in self.MODEL_IMPLEMENTATIONS.keys():
                self._log(f"  ├─ {available_type}", "yellow")
            return None
            
        if model_type not in self._models:
            key_name = self._get_api_key_mapping()[model_type]
            self._log(f"❌ Model type '{model_type}' not available - check {key_name} in .env", "red")
            return None
            
        model = self._models[model_type]
        if model_name and model.model_name != model_name:
            self._log(f"🔄 Reinitializing {model_type} with model {model_name}...", "cyan")
            # Create new instance with specified model name
            if api_key := os.getenv(self._get_api_key_mapping()[model_type]):
                try:
                    model = self.MODEL_IMPLEMENTATIONS[model_type](api_key, model_name=model_name)
                    self._models[model_type] = model
                    self._log(f"✨ Successfully reinitialized with new model", "green")
                except Exception as e:
                    self._log(f"❌ Failed to initialize {model_type} with model {model_name}", "red")
                    self._log(f"❌ Error type: {type(e).__name__}", "red")
                    self._log(f"❌ Error: {str(e)}", "red")
                    return None
            
        return model
    
    def _get_api_key_mapping(self) -> Dict[str, str]:
        """Get mapping of model types to their API key environment variable names"""
        return {
            "claude": "ANTHROPIC_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_KEY",
            "gemini": "GEMINI_KEY",
            "deepseek": "DEEPSEEK_KEY"
        }
    
    @property
    def available_models(self) -> Dict[str, list]:
        """Get all available models and their configurations"""
        return {
            model_type: model.AVAILABLE_MODELS
            for model_type, model in self._models.items()
        }
    
    def is_model_available(self, model_type: str) -> bool:
        """Check if a specific model type is available"""
        return model_type in self._models and self._models[model_type].is_available()

# Create a singleton instance with quiet mode from config
model_factory = ModelFactory(quiet_mode=MODEL_FACTORY_QUIET_MODE)

def create_model(model_type: str, model_name: Optional[str] = None, quiet: bool = None) -> Optional[BaseModel]:
    """Create a model instance using the factory"""
    if quiet is None:
        # Use config settings to determine quiet mode
        quiet = MODEL_FACTORY_QUIET_MODE or (not SHOW_DEBUG_IN_CONSOLE and LOG_LEVEL != "DEBUG")
    
    if quiet and hasattr(model_factory, 'quiet_mode'):
        # Temporarily enable quiet mode for this call
        original_quiet = model_factory.quiet_mode
        model_factory.quiet_mode = True
        result = model_factory.get_model(model_type, model_name)
        model_factory.quiet_mode = original_quiet
        return result
    else:
        return model_factory.get_model(model_type, model_name) 