import sys
import json
import logging
import shlex
from dataclasses import dataclass
from typing import Callable, Dict, List
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from src.agent import ZerePyAgent
from src.helpers import print_h_bar

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Command:
    """Dataclass to represent a CLI command"""
    name: str
    description: str
    tips: List[str]
    handler: Callable
    aliases: List[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []

class ZerePyCLI:
    def __init__(self):
        self.agent = None
        
        # Create config directory if it doesn't exist
        self.config_dir = Path.home() / '.zerepy'
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize command registry
        self._initialize_commands()
        
        # Setup prompt toolkit components
        self._setup_prompt_toolkit()

    def _initialize_commands(self) -> None:
        """Initialize all CLI commands"""
        self.commands: Dict[str, Command] = {}
        
        # Help command
        self._register_command(
            Command(
                name="help",
                description="Displays a list of all available commands, or help for a specific command.",
                tips=["Try 'help' to see available commands.",
                      "Try 'help {command}' to get more information about a specific command."],
                handler=self.help,
                aliases=['h', '?']
            )
        )
        
        ################## AGENTS ################## 
        # Agent action command
        self._register_command(
            Command(
                name="agent-action",
                description="Runs a single agent action.",
                tips=["Format: agent-action {connection} {action} [parameters]",
                      "Parameters can be positional: channel_id content",
                      "Or key=value format: channel_id=123 content=\"Hello World\"",
                      "Use 'list-connections' to see available connections.",
                      "Use 'list-actions' to see available actions."],
                handler=self.agent_action,
                aliases=['action', 'run']
            )
        )
        
        # Agent loop command
        self._register_command(
            Command(
                name="agent-loop",
                description="Starts the current agent's autonomous behavior loop.",
                tips=["Press Ctrl+C to stop the loop"],
                handler=self.agent_loop,
                aliases=['loop', 'start']
            )
        )
        
        # List agents command
        self._register_command(
            Command(
                name="list-agents",
                description="Lists all available agents you have on file.",
                tips=["Agents are stored in the 'agents' directory",
                      "Use 'load-agent' to load an available agent"],
                handler=self.list_agents,
                aliases=['agents', 'ls-agents']
            )
        )
        
        # Load agent command
        self._register_command(
            Command(
                name="load-agent",
                description="Loads an agent from a file.",
                tips=["Format: load-agent {agent_name}",
                      "Use 'list-agents' to see available agents"],
                handler=self.load_agent,
                aliases=['load']
            )
        )
        
        # Create agent command
        self._register_command(
            Command(
                name="create-agent",
                description="Creates a new agent.",
                tips=["Follow the interactive wizard to create a new agent"],
                handler=self.create_agent,
                aliases=['new-agent', 'create']
            )
        )
        
        # Define default agent
        self._register_command(
            Command(
                name="set-default-agent",
                description="Define which model is loaded when the CLI starts.",
                tips=["You can also just change the 'default_agent' field in agents/general.json"],
                handler=self.set_default_agent,
                aliases=['default']
            )
        )

        # Chat command
        self._register_command(
            Command(
                name="chat",
                description="Start a chat session with the current agent",
                tips=["Use 'exit' to end the chat session"],
                handler=self.chat_session,
                aliases=['talk']
            )
        )
        
        ################## CONTENT PIPELINE ##################
        # Start pipeline monitoring
        self._register_command(
            Command(
                name="start-pipeline",
                description="Start monitoring for new videos in the content pipeline",
                tips=["Pipeline will monitor cloud folder for new videos",
                      "Videos will be automatically processed, edited, and sent for review"],
                handler=self.start_pipeline,
                aliases=['pipeline-start']
            )
        )
        
        # Check pipeline status
        self._register_command(
            Command(
                name="pipeline-status",
                description="Check the status of content pipeline",
                tips=["Shows active pipelines and their current state"],
                handler=self.pipeline_status,
                aliases=['status']
            )
        )
        
        # Approve clip
        self._register_command(
            Command(
                name="approve-clip",
                description="Manually approve a clip for publishing",
                tips=["Format: approve-clip {video_id}",
                      "Use 'pipeline-status' to see pending clips"],
                handler=self.approve_clip,
                aliases=['approve']
            )
        )
        
        # Reject clip
        self._register_command(
            Command(
                name="reject-clip",
                description="Manually reject a clip",
                tips=["Format: reject-clip {video_id}"],
                handler=self.reject_clip,
                aliases=['reject']
            )
        )
        
        # List pipeline modes
        self._register_command(
            Command(
                name="list-modes",
                description="Show available pipeline modes",
                tips=["Displays all configured pipeline modes and their settings"],
                handler=self.list_modes,
                aliases=['modes']
            )
        )
        
        # Check compilation groups
        self._register_command(
            Command(
                name="check-compilations",
                description="Show pending compilation groups",
                tips=["Displays compilation groups waiting for timeout or more videos"],
                handler=self.check_compilation_groups,
                aliases=['compilations']
            )
        )
        
        ################## CONNECTIONS ################## 
        # List actions command
        self._register_command(
            Command(
                name="list-actions",
                description="Lists all available actions for the given connection.",
                tips=["Format: list-actions {connection}",
                      "Use 'list-connections' to see available connections"],
                handler=self.list_actions,
                aliases=['actions', 'ls-actions']
            )
        )
        
        # Configure connection command
        self._register_command(
            Command(
                name="configure-connection",
                description="Sets up a connection for API access.",
                tips=["Format: configure-connection {connection}",
                      "Follow the prompts to enter necessary credentials"],
                handler=self.configure_connection,
                aliases=['config', 'setup']
            )
        )
        
        # List connections command
        self._register_command(
            Command(
                name="list-connections",
                description="Lists all available connections.",
                tips=["Shows both configured and unconfigured connections"],
                handler=self.list_connections,
                aliases=['connections', 'ls-connections']
            )
        )
        
        ################## MISC ################## 
        # Exit command
        self._register_command(
            Command(
                name="exit",
                description="Exits the ZerePy CLI.",
                tips=["You can also use Ctrl+D to exit"],
                handler=self.exit,
                aliases=['quit', 'q']
            )
        )

    def _setup_prompt_toolkit(self) -> None:
        """Setup prompt toolkit components"""
        self.style = Style.from_dict({
            'prompt': 'ansicyan bold',
            'command': 'ansigreen',
            'error': 'ansired bold',
            'success': 'ansigreen bold',
            'warning': 'ansiyellow',
        })

        # Use FileHistory for persistent command history
        history_file = self.config_dir / 'history.txt'
        
        self.completer = WordCompleter(
            list(self.commands.keys()), 
            ignore_case=True,
            sentence=True
        )
        
        self.session = PromptSession(
            completer=self.completer,
            style=self.style,
            history=FileHistory(str(history_file))
        )

    ###################
    # Helper Functions
    ###################
    def _register_command(self, command: Command) -> None:
        """Register a command and its aliases"""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def _get_prompt_message(self) -> HTML:
        """Generate the prompt message based on current state"""
        agent_status = f"({self.agent.name})" if self.agent else "(no agent)"
        return HTML(f'<prompt>ZerePy-CLI</prompt> {agent_status} > ')

    def _handle_command(self, input_string: str) -> None:
        """Parse and handle a command input"""
        try:
            # Use shlex.split() to properly handle quoted strings with spaces
            input_list = shlex.split(input_string)
        except ValueError as e:
            # If shlex parsing fails (e.g., unmatched quotes), fall back to simple split
            logger.error(f"Error parsing command: {e}")
            logger.info("Tip: Make sure quotes are properly matched")
            input_list = input_string.split()
        
        if not input_list:
            return
        
        # Post-process to handle key=value pairs where quoted value was split
        # Only join if shlex actually split a quoted value (value is empty or very short)
        processed_list = []
        i = 0
        while i < len(input_list):
            token = input_list[i]
            # Check if this is a key=value pair
            if '=' in token:
                key, value_part = token.split('=', 1)
                # Only join if:
                # 1. Value part is empty or very short (suggests it was split)
                # 2. Next token exists and doesn't have '='
                # 3. We haven't seen another key=value pair yet
                if (not value_part or len(value_part) < 3) and \
                   i + 1 < len(input_list) and '=' not in input_list[i + 1]:
                    # This might be a split quoted value - collect continuation tokens
                    value_parts = [value_part] if value_part else []
                    i += 1
                    # Collect all following tokens that don't have '=' as part of the value
                    while i < len(input_list) and '=' not in input_list[i]:
                        value_parts.append(input_list[i])
                        i += 1
                    # Join with spaces and create single key=value token
                    if value_parts:
                        processed_list.append(f"{key}={' '.join(value_parts)}")
                        continue
            processed_list.append(token)
            i += 1
        
        input_list = processed_list
        command_string = input_list[0].lower()

        try:
            command = self.commands.get(command_string)
            if command:
                command.handler(input_list)
            else:
                self._handle_unknown_command(command_string)
        except Exception as e:
            logger.error(f"Error executing command: {e}")

    def _handle_unknown_command(self, command: str) -> None:
        """Handle unknown command with suggestions"""
        logger.warning(f"Unknown command: '{command}'") 

        # Suggest similar commands using basic string similarity
        suggestions = self._get_command_suggestions(command)
        if suggestions:
            logger.info("Did you mean one of these?")
            for suggestion in suggestions:
                logger.info(f"  - {suggestion}")
        logger.info("Use 'help' to see all available commands.")

    def _get_command_suggestions(self, command: str, max_suggestions: int = 3) -> List[str]:
        """Get command suggestions based on string similarity"""
        from difflib import get_close_matches
        return get_close_matches(command, self.commands.keys(), n=max_suggestions, cutoff=0.6)

    def _print_welcome_message(self) -> None:
        """Print welcome message and initial status"""
        print_h_bar()
        logger.info("👋 Welcome to the ZerePy CLI!")
        logger.info("Type 'help' for a list of commands.")
        print_h_bar() 

    def _show_command_help(self, command_name: str) -> None:
        """Show help for a specific command"""
        command = self.commands.get(command_name)
        if not command:
            logger.warning(f"Unknown command: '{command_name}'")
            suggestions = self._get_command_suggestions(command_name)
            if suggestions:
                logger.info("Did you mean one of these?")
                for suggestion in suggestions:
                    logger.info(f"  - {suggestion}")
            return

        logger.info(f"\nHelp for '{command.name}':")
        logger.info(f"Description: {command.description}")
        
        if command.aliases:
            logger.info(f"Aliases: {', '.join(command.aliases)}")
        
        if command.tips:
            logger.info("\nTips:")
            for tip in command.tips:
                logger.info(f"  - {tip}")

    def _show_general_help(self) -> None:
        """Show general help information"""
        logger.info("\nAvailable Commands:")
        # Group commands by first letter for better organization
        commands_by_letter = {}
        for cmd_name, cmd in self.commands.items():
            # Only show main commands, not aliases
            if cmd_name == cmd.name:
                first_letter = cmd_name[0].upper()
                if first_letter not in commands_by_letter:
                    commands_by_letter[first_letter] = []
                commands_by_letter[first_letter].append(cmd)

        for letter in sorted(commands_by_letter.keys()):
            logger.info(f"\n{letter}:")
            for cmd in sorted(commands_by_letter[letter], key=lambda x: x.name):
                logger.info(f"  {cmd.name:<15} - {cmd.description}")

    def _list_loaded_agent(self) -> None:
        if self.agent:
            logger.info(f"\nStart the agent loop with the command 'start' or use one of the action commands.")
        else:
            logger.info(f"\nNo default agent is loaded, please use the load-agent command to do that.")

    def _load_agent_from_file(self, agent_name):
        try: 
            self.agent = ZerePyAgent(agent_name)
            logger.info(f"\n✅ Successfully loaded agent: {self.agent.name}")
        except FileNotFoundError:
            logger.error(f"Agent file not found: {agent_name}")
            logger.info("Use 'list-agents' to see available agents.")
        except KeyError as e:
            logger.error(f"Invalid agent file: {e}")
        except Exception as e:
            logger.error(f"Error loading agent: {e}")

    def _load_default_agent(self) -> None:
        """Load users default agent"""
        agent_general_config_path = Path("agents") / "general.json"
        file = None
        try:
            file = open(agent_general_config_path, 'r')
            data = json.load(file)
            if not data.get('default_agent'):
                logger.error('No default agent defined, please set one in general.json')
                return

            self._load_agent_from_file(data.get('default_agent'))
        except FileNotFoundError:
            logger.error("File general.json not found, please create one.")
            return
        except json.JSONDecodeError:
            logger.error("File agents/general.json contains Invalid JSON format")
            return
        finally:
            if file:
                file.close()
    
    ###################
    # Command functions
    ###################
    def help(self, input_list: List[str]) -> None:
        """List all commands supported by the CLI"""
        if len(input_list) > 1:
            self._show_command_help(input_list[1])
        else:
            self._show_general_help()

    def agent_action(self, input_list: List[str]) -> None:
        """Handle agent action command"""
        if self.agent is None:
            logger.info("No agent is currently loaded. Use 'load-agent' to load an agent.")
            return

        if len(input_list) < 3:
            logger.info("Please specify both a connection and an action.")
            logger.info("Format: agent-action {connection} {action}")
            return

        try:
            result = self.agent.perform_action(
                connection=input_list[1],
                action=input_list[2],
                params=input_list[3:]
            )
            logger.info(f"Result: {result}")
        except Exception as e:
            logger.error(f"Error running action: {e}")

    def agent_loop(self, input_list: List[str]) -> None:
        """Handle agent loop command"""
        if self.agent is None:
            logger.info("No agent is currently loaded. Use 'load-agent' to load an agent.")
            return

        # Auto-configure YouTube if not configured
        if not self.agent.connection_manager.connections.get("youtube", {}).is_configured():
            logger.info("\n🔧 YouTube not configured. Setting up automatically...")
            try:
                self.agent.connection_manager.configure_connection("youtube")
                logger.info("✅ YouTube configured successfully!")
            except Exception as e:
                logger.warning(f"⚠️ YouTube auto-configuration failed: {e}")
                logger.info("You can manually configure YouTube later with 'configure-connection youtube'")
                logger.info("Continuing with available connections...")

        try:
            self.agent.loop()
        except KeyboardInterrupt:
            logger.info("\n🛑 Agent loop stopped by user.")
        except Exception as e:
            logger.error(f"Error in agent loop: {e}")

    def list_agents(self, input_list: List[str]) -> None:
        """Handle list agents command"""
        logger.info("\nAvailable Agents:")
        agents_dir = Path("agents")
        if not agents_dir.exists():
            logger.info("No agents directory found.")
            return

        agents = list(agents_dir.glob("*.json"))
        if not agents:
            logger.info("No agents found. Use 'create-agent' to create a new agent.")
            return

        for agent_file in sorted(agents):
            if agent_file.stem == "general":
                continue
            logger.info(f"- {agent_file.stem}")

    def load_agent(self, input_list: List[str]) -> None:
        """Handle load agent command"""
        if len(input_list) < 2:
            logger.info("Please specify an agent name.")
            logger.info("Format: load-agent {agent_name}")
            logger.info("Use 'list-agents' to see available agents.")
            return

        self._load_agent_from_file(agent_name=input_list[1])
    
    def create_agent(self, input_list: List[str]) -> None:
        """Handle create agent command"""
        logger.info("\nℹ️ Agent creation wizard not implemented yet.")
        logger.info("Please create agent JSON files manually in the 'agents' directory.")
    
    def set_default_agent(self, input_list: List[str]):
        """Handle set-default-agent command"""
        if len(input_list) < 2:
            logger.info("Please specify the same of the agent file.")
            return
        
        agent_general_config_path = Path("agents") / "general.json"
        file = None
        try:
            file = open(agent_general_config_path, 'r')
            data = json.load(file)
            agent_file_name = input_list[1]
            # if file does not exist, refuse to set it as default
            try:
                agent_path = Path("agents") / f"{agent_file_name}.json"
                open(agent_path, 'r')
            except FileNotFoundError:
                logging.error("Agent file not found.")
                return
            
            data['default_agent'] = input_list[1]
            with open(agent_general_config_path, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Agent {agent_file_name} is now set as default.")
        except FileNotFoundError:
            logger.error("File not found")
            return
        except json.JSONDecodeError:
            logger.error("Invalid JSON format")
            return
        finally:
            if file:
                file.close()

    def list_actions(self, input_list: List[str]) -> None:
        """Handle list actions command"""
        if len(input_list) < 2:
            logger.info("\nPlease specify a connection.")
            logger.info("Format: list-actions {connection}")
            logger.info("Use 'list-connections' to see available connections.")
            return

        self.agent.connection_manager.list_actions(connection_name=input_list[1])

    def configure_connection(self, input_list: List[str]) -> None:
        """Handle configure connection command"""
        if len(input_list) < 2:
            logger.info("\nPlease specify a connection to configure.")
            logger.info("Format: configure-connection {connection}")
            logger.info("Use 'list-connections' to see available connections.")
            return

        self.agent.connection_manager.configure_connection(connection_name=input_list[1])

    def list_connections(self, input_list: List[str] = []) -> None:
        """Handle list connections command"""
        if self.agent:
            self.agent.connection_manager.list_connections()
        else:
            logging.info("Please load an agent to see the list of supported actions")

    def chat_session(self, input_list: List[str]) -> None:
        """Handle chat command"""
        if self.agent is None:
            logger.info("No agent loaded. Use 'load-agent' first.")
            return

        if not self.agent.is_llm_set:
            self.agent._setup_llm_provider()

        logger.info(f"\nStarting chat with {self.agent.name}")
        print_h_bar()

        while True:
            try:
                user_input = self.session.prompt("\nYou: ").strip()
                if user_input.lower() == 'exit':
                    break
                
                response = self.agent.prompt_llm(user_input)
                logger.info(f"\n{self.agent.name}: {response}")
                print_h_bar()
                
            except KeyboardInterrupt:
                break

    def exit(self, input_list: List[str]) -> None:
        """Exit the CLI gracefully"""
        # Cleanup connections
        if self.agent:
            for name, connection in self.agent.connection_manager.connections.items():
                if hasattr(connection, 'cleanup'):
                    try:
                        connection.cleanup()
                    except Exception as e:
                        logger.warning(f"Error cleaning up {name} connection: {e}")
        
        logger.info("\nGoodbye! 👋")
        sys.exit(0)

    def start_pipeline(self, input_list: List[str]) -> None:
        """Handle start-pipeline command"""
        if self.agent is None:
            logger.info("No agent loaded. Use 'load-agent' first.")
            return

        logger.info("\n🚀 Starting Content Pipeline...")
        logger.info("This will monitor for new videos and process them automatically.")
        logger.info("Press Ctrl+C to stop.\n")

        try:
            # Import pipeline components
            from src.pipeline_manager import ContentPipeline
            from src.agents.gallery_agent import GalleryAgent
            from src.agents.compliance_agent import ComplianceAgent

            # Initialize pipeline
            pipeline = ContentPipeline()

            # Check for required environment variables
            import os
            if not os.getenv("GMAIL_APP_PASSWORD"):
                logger.warning("⚠️  GMAIL_APP_PASSWORD not found in environment variables")
                logger.warning("Email notifications will not work without this setting")
                logger.warning("Add GMAIL_APP_PASSWORD=your_app_password to your .env file")

            # Initialize compliance agent if configured
            from config import COMPLIANCE_CONFIG

            if COMPLIANCE_CONFIG["enabled"]:
                logger.info("🔍 Initializing compliance agent...")
                try:
                    # Get DeepSeek connection for AI analysis
                    deepseek_conn = self.agent.connection_manager.connections.get("deepseek")

                    if not deepseek_conn:
                        logger.warning("⚠️  DeepSeek connection not available for compliance agent")
                        logger.info("⚠️  Pipeline will continue without compliance checks")
                    else:
                        compliance_agent = ComplianceAgent(
                            platform=COMPLIANCE_CONFIG["platform"],
                            deepseek_connection=deepseek_conn
                        )
                        pipeline.set_compliance_agent(compliance_agent)
                        logger.info("✅ Compliance agent ready")
                except Exception as e:
                    logger.warning(f"Failed to initialize compliance agent: {e}")
                    logger.info("⚠️  Pipeline will continue without compliance checks")

            # Get gallery configuration
            from config import GALLERY_CONFIG
            cloud_folder = GALLERY_CONFIG["cloud_folder_path"]

            if not cloud_folder:
                logger.error("❌ No cloud_folder_path configured in GALLERY_CONFIG")
                return

            # Verify cloud folder exists
            from pathlib import Path
            cloud_path = Path(cloud_folder)
            if not cloud_path.exists():
                logger.error(f"❌ Cloud folder does not exist: {cloud_folder}")
                logger.error("Please ensure iCloud Drive is set up and the path is correct")
                logger.error("You can update the path in config.py GALLERY_CONFIG")
                return

            if not cloud_path.is_dir():
                logger.error(f"❌ Cloud folder path is not a directory: {cloud_folder}")
                return

            logger.info(f"📂 Cloud folder verified: {cloud_folder}")

            # Initialize gallery agent
            logger.info("🎥 Initializing gallery agent...")
            try:
                gallery_agent = GalleryAgent(pipeline_manager=pipeline)
            except Exception as e:
                logger.error(f"❌ Failed to initialize gallery agent: {e}")
                logger.error("This might be due to missing cloud folder or permissions")
                return

            logger.info("🔍 Starting file monitoring...")
            try:
                gallery_agent.start_monitoring()
            except Exception as e:
                logger.error(f"❌ Failed to start file monitoring: {e}")
                logger.error("This might be due to folder access issues or watchdog problems")
                return

            logger.info("✅ Pipeline monitoring started!")
            logger.info(f"Watching folder: {cloud_folder}")
            logger.info("📡 System will continue monitoring for new videos...")
            logger.info("Press Ctrl+C to stop monitoring\n")

            # Keep running indefinitely
            monitoring_active = True
            while monitoring_active:
                try:
                    import time
                    time.sleep(1)

                    # Periodic health check every 60 seconds
                    import time as time_module
                    if int(time_module.time()) % 60 == 0:
                        logger.debug("📊 Pipeline monitoring active...")

                except KeyboardInterrupt:
                    logger.info("\n🛑 Received stop signal...")
                    monitoring_active = False
                except Exception as e:
                    logger.error(f"⚠️  Unexpected error in monitoring loop: {e}")
                    logger.info("🔄 Attempting to continue monitoring...")
                    import time
                    time.sleep(5)  # Brief pause before continuing

            # Cleanup
            logger.info("🧹 Stopping gallery agent...")
            gallery_agent.stop_monitoring()
            logger.info("🛑 Pipeline monitoring stopped")

        except Exception as e:
            logger.error(f"Failed to start pipeline: {e}")
            import traceback
            traceback.print_exc()

    def pipeline_status(self, input_list: List[str]) -> None:
        """Handle pipeline-status command"""
        try:
            import time as time_module
            from src.pipeline_manager import ContentPipeline

            pipeline = ContentPipeline()
            active_pipelines = pipeline.get_active_pipelines()

            if not active_pipelines:
                logger.info("\n📊 No active pipelines")
                return

            logger.info(f"\n📊 Active Pipelines ({len(active_pipelines)}):")
            print_h_bar()

            for p in active_pipelines:
                logger.info(f"\nVideo ID: {p['video_id']}")
                logger.info(f"  File: {p['original_filename']}")
                logger.info(f"  State: {p['state']}")
                logger.info(f"  Mode: {p.get('mode', 'talking_head')} 🎭")
                
                # Show compilation group if applicable
                if p.get('compilation_group_id'):
                    logger.info(f"  Compilation Group: {p['compilation_group_id']}")
                
                logger.info(f"  Created: {time_module.strftime('%Y-%m-%d %H:%M:%S', time_module.localtime(p['created_at']))}")

                # Get clips for this video
                clips = pipeline.get_clips_for_video(p['video_id'])
                if clips:
                    logger.info(f"  Clips: {len(clips)} generated")
                    for clip in clips:
                        status = "✅ Approved" if clip['approved'] else "⏳ Pending"
                        logger.info(f"    - Clip {clip['clip_id'][:8]}... ({status}, score: {clip.get('score', 0):.2f})")

            print_h_bar()

        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")

    def approve_clip(self, input_list: List[str]) -> None:
        """Handle approve-clip command"""
        if len(input_list) < 2:
            logger.info("\nPlease specify a video ID")
            logger.info("Format: approve-clip {video_id}")
            logger.info("Use 'pipeline-status' to see pending videos")
            return

        try:
            from src.pipeline_manager import ContentPipeline

            video_id = input_list[1]
            pipeline = ContentPipeline()

            # Get clips for video
            clips = pipeline.get_clips_for_video(video_id)
            if not clips:
                logger.error(f"No clips found for video {video_id}")
                return

            # Approve the highest-scored clip
            best_clip = max(clips, key=lambda c: c.get('score', 0))
            pipeline.handle_review_response(video_id, best_clip['clip_id'], approved=True)

            logger.info(f"\n✅ Clip approved!")
            logger.info(f"Video ID: {video_id}")
            logger.info(f"Clip ID: {best_clip['clip_id']}")
            logger.info(f"\nThe clip will be published to YouTube Shorts")

        except Exception as e:
            logger.error(f"Failed to approve clip: {e}")

    def reject_clip(self, input_list: List[str]) -> None:
        """Handle reject-clip command"""
        if len(input_list) < 2:
            logger.info("\nPlease specify a video ID")
            logger.info("Format: reject-clip {video_id}")
            return

        try:
            from src.pipeline_manager import ContentPipeline

            video_id = input_list[1]
            pipeline = ContentPipeline()

            # Get clips for video
            clips = pipeline.get_clips_for_video(video_id)
            if not clips:
                logger.error(f"No clips found for video {video_id}")
                return

            # Reject all clips
            for clip in clips:
                pipeline.handle_review_response(video_id, clip['clip_id'], approved=False)

            logger.info(f"\n❌ All clips rejected for video {video_id}")

        except Exception as e:
            logger.error(f"Failed to reject clip: {e}")
    
    def list_modes(self, input_list: List[str]) -> None:
        """Handle list-modes command"""
        try:
            from config import PIPELINE_MODES, get_enabled_modes
            
            logger.info("\n" + "="*60)
            logger.info("📋 AVAILABLE PIPELINE MODES")
            logger.info("="*60)
            
            enabled_modes = get_enabled_modes()
            logger.info(f"\n✅ Enabled Modes: {', '.join(enabled_modes)}\n")
            
            for mode, config in PIPELINE_MODES.items():
                status = "✅ ENABLED" if config.get("enabled") else "⏸️  DISABLED"
                logger.info(f"\n{status} - {mode.upper()}")
                logger.info(f"{'='*60}")
                logger.info(f"Description: {config.get('description', 'N/A')}")
                logger.info(f"Input Type: {config.get('input_type', 'N/A')}")
                
                # Show processing steps
                steps = config.get('processing_steps', [])
                if steps:
                    logger.info(f"Processing Steps: {' → '.join(steps)}")
                
                # Show editing profile
                editing = config.get('editing_profile', {})
                if editing:
                    logger.info(f"Editing Profile:")
                    for key, value in editing.items():
                        logger.info(f"  - {key}: {value}")
                
                # Mode-specific details
                if mode == "condensation":
                    logger.info(f"Preserve Flow: {config.get('preserve_narrative_flow', False)}")
                elif mode == "compilation":
                    logger.info(f"Max Videos: {config.get('max_source_videos', 'N/A')}")
                elif mode == "ai_generation":
                    providers = config.get('api_providers', {})
                    configured = [p for p, c in providers.items() if c.get('enabled')]
                    if configured:
                        logger.info(f"Configured APIs: {', '.join(configured)}")
                    else:
                        logger.info("⚠️  No AI APIs configured")
            
            logger.info("\n" + "="*60)
            logger.info("\n💡 To use a specific mode:")
            logger.info("  - Place videos in the appropriate folder (e.g., 'videos_condensation')")
            logger.info("  - Or use filename prefixes (e.g., 'condense_myvideo.mp4')")
            logger.info("  - Mode will be automatically detected\n")
            
        except Exception as e:
            logger.error(f"Failed to list modes: {e}")
            import traceback
            traceback.print_exc()
    
    def check_compilation_groups(self, input_list: List[str]) -> None:
        """Handle check-compilations command"""
        try:
            from src.pipeline_manager import ContentPipeline
            from config import COMPILATION_CONFIG
            
            pipeline = ContentPipeline()
            
            logger.info("\n" + "="*60)
            logger.info("🎬 COMPILATION GROUPS")
            logger.info("="*60)
            
            # Get all compilation groups
            groups = pipeline.get_compilation_groups()
            
            if not groups:
                logger.info("\n📊 No compilation groups found")
                logger.info("\nTo create a compilation:")
                logger.info("  1. Place multiple videos in a folder named 'videos_compilation'")
                logger.info("  2. Or use 'compile_' prefix for filenames")
                logger.info(f"  3. Videos will compile after {COMPILATION_CONFIG.get('timeout_minutes', 5)} minutes\n")
                return
            
            # Separate by state
            collecting = [g for g in groups if g.get('state') == 'collecting']
            processing = [g for g in groups if g.get('state') == 'processing']
            
            if collecting:
                logger.info(f"\n⏳ COLLECTING ({len(collecting)} groups):")
                for group in collecting:
                    group_id = group['group_id']
                    video_count = group['video_count']
                    timeout_at = group['timeout_at']
                    folder = Path(group['folder_path']).name
                    
                    # Calculate time remaining
                    import time
                    time_remaining = timeout_at - time.time()
                    minutes_remaining = int(time_remaining / 60)
                    seconds_remaining = int(time_remaining % 60)
                    
                    logger.info(f"\n  Group: {group_id}")
                    logger.info(f"  Folder: {folder}")
                    logger.info(f"  Videos: {video_count}")
                    if time_remaining > 0:
                        logger.info(f"  Timeout: {minutes_remaining}m {seconds_remaining}s remaining")
                    else:
                        logger.info(f"  Timeout: READY (processing soon)")
            
            if processing:
                logger.info(f"\n🎬 PROCESSING ({len(processing)} groups):")
                for group in processing:
                    group_id = group['group_id']
                    video_count = group['video_count']
                    folder = Path(group['folder_path']).name
                    
                    logger.info(f"\n  Group: {group_id}")
                    logger.info(f"  Folder: {folder}")
                    logger.info(f"  Videos: {video_count}")
                    logger.info(f"  Status: Currently compiling...")
            
            logger.info("\n" + "="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Failed to check compilation groups: {e}")
            import traceback
            traceback.print_exc()

    ###################
    # Main CLI Loop
    ###################
    def main_loop(self) -> None:
        """Main CLI loop"""
        self._print_welcome_message()
        self._load_default_agent()
        self._list_loaded_agent()
        self.list_connections()
        
        # Start CLI loop
        while True:
            try:
                input_string = self.session.prompt(
                    self._get_prompt_message(),
                    style=self.style
                ).strip()

                if not input_string:
                    continue

                self._handle_command(input_string)
                print_h_bar()

            except KeyboardInterrupt:
                logger.info("\n\nInterrupted. Use 'exit' to quit gracefully.")
                continue
            except EOFError:
                self.exit([])
            except Exception as e:
                logger.exception(f"Unexpected error: {e}") 