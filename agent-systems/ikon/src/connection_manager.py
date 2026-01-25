import logging
from typing import Any, List, Optional, Type, Dict
from src.connections.base_connection import BaseConnection
from src.connections.anthropic_connection import AnthropicConnection
from src.connections.openai_connection import OpenAIConnection
from src.connections.twitter_connection import TwitterConnection
from src.connections.discord_connection import DiscordConnection
from src.connections.youtube_connection import YouTubeConnection
from src.connections.deepseek_connection import DeepSeekConnection

logger = logging.getLogger("connection_manager")

class ConnectionManager:
    def __init__(self, agent_config):
        self.connections : Dict[str, BaseConnection] = {}
        for config in agent_config:
            self._register_connection(config)
    
    @staticmethod
    def _class_name_to_type(class_name: str) -> Type[BaseConnection]:
        if class_name == "twitter":
            return TwitterConnection
        elif class_name == "discord":
            return DiscordConnection
        elif class_name == "youtube":
            return YouTubeConnection
        elif class_name == "deepseek":
            return DeepSeekConnection
        elif class_name == "anthropic":
            return AnthropicConnection
        elif class_name == "openai":
            return OpenAIConnection

        return None
    
    def _register_connection(self, config_dic: Dict[str, Any]) -> None:
        """
        Create and register a new connection with configuration
        
        Args:
            name: Identifier for the connection
            connection_class: The connection class to instantiate
            config: Configuration dictionary for the connection
        """
        try:
            name = config_dic["name"]
            connection_class = self._class_name_to_type(name)
            connection = connection_class(config_dic)
            self.connections[name] = connection
        except Exception as e:
            logging.error(f"Failed to initialize connection {name}: {e}")

    def _check_connection(self, connection_string: str)-> bool:
        try:
            connection = self.connections[connection_string]
            return connection.is_configured(verbose=True)
        except KeyError:
            logging.error("\nUnknown connection. Try 'list-connections' to see all supported connections.")
            return False
        except Exception as e:
            logging.error(f"\nAn error occurred: {e}")
            return False

    def configure_connection(self, connection_name: str) -> bool:
        """Configure a specific connection"""
        try:
            connection = self.connections[connection_name]
            success = connection.configure()
            
            if success:
                logging.info(f"\n✅ SUCCESSFULLY CONFIGURED CONNECTION: {connection_name}")
            else:
                logging.error(f"\n❌ ERROR CONFIGURING CONNECTION: {connection_name}")
            return success
            
        except KeyError:
            logging.error("\nUnknown connection. Try 'list-connections' to see all supported connections.")
            return False
        except Exception as e:
            logging.error(f"\nAn error occurred: {e}")
            return False

    def list_connections(self) -> None:
        """List all available connections and their status"""
        logging.info("\nAVAILABLE CONNECTIONS:")
        for name, connection in self.connections.items():
            status = "✅ Configured" if connection.is_configured() else "❌ Not Configured"
            logging.info(f"- {name}: {status}")

    def list_actions(self, connection_name: str) -> None:
        """List all available actions for a specific connection"""
        try:
            connection = self.connections[connection_name]
            
            if connection.is_configured():
                logging.info(f"\n✅ {connection_name} is configured. You can use any of its actions.")
            else:
                logging.info(f"\n❌ {connection_name} is not configured. You must configure a connection to use its actions.")
            
            logging.info("\nAVAILABLE ACTIONS:")
            for action_name, action in connection.actions.items():
                logging.info(f"- {action_name}: {action.description}")
                logging.info("  Parameters:")
                for param in action.parameters:
                    req = "required" if param.required else "optional"
                    logging.info(f"    - {param.name} ({req}): {param.description}")
                
        except KeyError:
            logging.error("\nUnknown connection. Try 'list-connections' to see all supported connections.")
        except Exception as e:
            logging.error(f"\nAn error occurred: {e}")

    def perform_action(self, connection_name: str, action_name: str, params: List[Any]) -> Optional[Any]:
        """Perform an action on a specific connection with given parameters"""
        try:
            connection = self.connections[connection_name]
            
            if not connection.is_configured():
                logging.error(f"\nError: Connection '{connection_name}' is not configured")
                return None
                
            if action_name not in connection.actions:
                logging.error(f"\nError: Unknown action '{action_name}' for connection '{connection_name}'")
                return None
                
            action = connection.actions[action_name]
            
            # Parse parameters - support both key=value and positional formats
            kwargs = {}

            # Check if parameters contain key=value pairs
            has_key_value_pairs = any('=' in str(param) for param in params)

            if has_key_value_pairs:
                # Parse key=value pairs
                for param_str in params:
                    param_str = str(param_str).strip()
                    if '=' in param_str:
                        try:
                            key, value = param_str.split('=', 1)
                            key = key.strip()
                            value = value.strip()

                            # Handle quoted values
                            if (value.startswith('"') and value.endswith('"')) or \
                               (value.startswith("'") and value.endswith("'")):
                                value = value[1:-1]  # Remove quotes

                            kwargs[key] = value
                        except ValueError:
                            logging.error(f"\nError: Invalid key=value parameter format: {param_str}")
                            return None
                    else:
                        logging.error(f"\nError: Mixed parameter formats. Use either all positional or all key=value: {param_str}")
                        return None
            else:
                # Use positional parameters (backward compatibility)
                required_params_count = sum(1 for param in action.parameters if param.required)

                # Check if we have enough parameters
                if len(params) != required_params_count:
                    param_names = [param.name for param in action.parameters if param.required]
                    logging.error(f"\nError: Expected {required_params_count} required parameters for {action_name}: {', '.join(param_names)}")
                    logging.info("You can also use key=value format: agent-action {connection} {action} key1=value1 key2=value2")
                    return None

                # Convert list of params to kwargs dictionary
                param_index = 0
                for param in action.parameters:
                    if param.required:
                        kwargs[param.name] = params[param_index]
                        param_index += 1

            # Validate that all required parameters are provided
            missing_params = []
            for param in action.parameters:
                if param.required and param.name not in kwargs:
                    missing_params.append(param.name)

            if missing_params:
                logging.error(f"\nError: Missing required parameters: {', '.join(missing_params)}")
                return None
            
            return connection.perform_action(action_name, kwargs)
            
        except Exception as e:
            logging.error(f"\nAn error occurred while trying action {action_name} for {connection_name} connection: {e}")
            return None

    def get_model_providers(self) -> List[str]:
        """Get a list of all LLM provider connections"""
        return [
            name for name, conn in self.connections.items() 
            if conn.is_configured() and getattr(conn, 'is_llm_provider', lambda: False)
        ]