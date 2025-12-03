import logging
import os
from typing import Dict, Any
import openai

from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import find_env_file

logger = logging.getLogger(__name__)

class DeepSeekConnectionError(Exception):
    """Base exception for DeepSeek connection errors"""
    pass

class DeepSeekConfigurationError(DeepSeekConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class DeepSeekAPIError(DeepSeekConnectionError):
    """Raised when DeepSeek API requests fail"""
    pass

class DeepSeekConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return True

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate DeepSeek configuration from JSON"""
        required_fields = ["model"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        # Validate model - DeepSeek supports these models
        valid_models = ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]
        if config["model"] not in valid_models:
            logger.warning(f"Model '{config['model']}' may not be valid. Valid models: {', '.join(valid_models)}")

        if not isinstance(config["model"], str):
            raise ValueError("model must be a string")

        return config

    def register_actions(self) -> None:
        """Register available DeepSeek actions"""
        self.actions = {
            "generate-text": Action(
                name="generate-text",
                parameters=[
                    ActionParameter("prompt", True, str, "The input prompt for text generation"),
                    ActionParameter("system_prompt", False, str, "System prompt to set context and behavior"),
                    ActionParameter("model", False, str, "DeepSeek model to use (defaults to config)"),
                    ActionParameter("temperature", False, float, "Creativity/randomness (0.0-2.0, default 0.7)"),
                    ActionParameter("max_tokens", False, int, "Maximum tokens to generate (default 400)"),
                ],
                description="Generate text using DeepSeek AI models"
            ),
        }

    def _get_client(self):
        """Get or create OpenAI-compatible DeepSeek client"""
        if self._client is None:
            # Find and load .env file from parent directories
            find_env_file()
            
            api_key = os.getenv('DEEPSEEK_KEY')
            if not api_key:
                raise DeepSeekConfigurationError("DEEPSEEK_KEY not found in environment variables")

            try:
                self._client = openai.OpenAI(
                    api_key=api_key,
                    base_url="https://api.deepseek.com"
                )
                logger.debug("DeepSeek client initialized successfully")
            except Exception as e:
                raise DeepSeekConfigurationError(f"Failed to initialize DeepSeek client: {str(e)}")

        return self._client

    def configure(self) -> bool:
        """Configure DeepSeek API access"""
        logger.info("Configuring DeepSeek API connection")

        try:
            # Find and load .env file from parent directories
            find_env_file()
            
            # Check if API key is available
            api_key = os.getenv('DEEPSEEK_KEY')
            if not api_key:
                logger.error("DEEPSEEK_KEY environment variable not found")
                logger.info("Please set DEEPSEEK_KEY in your .env file")
                logger.info("Get your API key from: https://platform.deepseek.com/")
                return False

            # Test the connection
            client = self._get_client()

            # Test with a simple API call
            try:
                response = client.chat.completions.create(
                    model=self.config["model"],
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10
                )
                logger.info("✅ DeepSeek API connection successful!")
                logger.info(f"Using model: {self.config['model']}")
                return True

            except Exception as e:
                logger.error(f"DeepSeek API test failed: {str(e)}")
                if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                    logger.error("Check your DEEPSEEK_KEY - it may be invalid")
                return False

        except Exception as e:
            logger.error(f"DeepSeek configuration failed: {str(e)}")
            return False

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if DeepSeek API is configured and accessible"""
        try:
            # Check if API key exists in environment
            api_key = os.getenv('DEEPSEEK_KEY')
            if not api_key:
                if verbose:
                    logger.error("DEEPSEEK_KEY environment variable not set")
                return False

            # Quick validation: just check if key looks valid (starts with sk-)
            if not api_key.startswith('sk-'):
                if verbose:
                    logger.warning("DEEPSEEK_KEY format may be invalid")
                return False

            # For quick checks, just verify key exists and looks valid
            # Don't make API calls during is_configured() check to avoid blocking CLI
            logger.debug("DeepSeek API key found and format valid")
            return True

        except Exception as e:
            if verbose:
                logger.error(f"DeepSeek configuration validation failed: {str(e)}")
            return False

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a DeepSeek action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)
        return method(**kwargs)

    def generate_text(self, prompt: str, system_prompt: str = None, model: str = None,
                     temperature: float = 0.7, max_tokens: int = 400, **kwargs) -> str:
        """Generate text using DeepSeek models"""
        try:
            client = self._get_client()

            # Use specified model or default from config
            model_to_use = model or self.config["model"]

            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # Make API call
            response = client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=min(max(temperature, 0.0), 2.0),  # Clamp to valid range
                max_tokens=min(max_tokens, 4096),  # Reasonable limit
                stream=False
            )

            # Extract response
            if response.choices and len(response.choices) > 0:
                generated_text = response.choices[0].message.content
                if generated_text:
                    logger.debug(f"Generated {len(generated_text)} characters with DeepSeek")
                    return generated_text.strip()

            raise DeepSeekAPIError("No content generated by DeepSeek")

        except Exception as e:
            error_msg = f"DeepSeek text generation failed: {str(e)}"
            logger.error(error_msg)
            raise DeepSeekAPIError(error_msg)
