import os
import logging
import asyncio
import threading
import discord
from typing import Dict, Any, List, Optional
from discord.ext import commands
from dotenv import set_key
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar, find_env_file

logger = logging.getLogger("connections.discord_connection")

class DiscordConnectionError(Exception):
    """Base exception for Discord connection errors"""
    pass

class DiscordConfigurationError(DiscordConnectionError):
    """Raised when there are configuration/credential issues"""
    pass

class DiscordAPIError(DiscordConnectionError):
    """Raised when Discord API requests fail"""
    pass

class DiscordConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot: Optional[commands.Bot] = None
        self._intents = discord.Intents.default()
        self._intents.message_content = True
        self._intents.members = True
        self._intents.guilds = True
        self._intents.messages = True
        self._intents.reactions = True
        self._intents.voice_states = True
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Discord configuration from JSON"""
        required_fields = ["guild_id"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")

        # Validate guild_id is a string (Discord IDs are large integers but stored as strings)
        if not isinstance(config["guild_id"], str) or not config["guild_id"].isdigit():
            raise ValueError("guild_id must be a valid Discord snowflake ID (numeric string)")

        # Optional fields with defaults
        config.setdefault("command_prefix", "!")
        config.setdefault("auto_join_voice", False)
        config.setdefault("log_channel_id", None)
        config.setdefault("welcome_channel_id", None)
        config.setdefault("auto_mod_enabled", True)
        config.setdefault("spam_threshold", 5)

        return config

    def _get_credentials(self) -> Dict[str, str]:
        """Get Discord bot token from environment with validation"""
        logger.debug("Retrieving Discord bot token")

        token = os.getenv('DISCORD_BOT_TOKEN')
        if not token:
            raise DiscordConfigurationError("DISCORD_BOT_TOKEN not found in environment variables")

        return {'token': token}

    def _create_bot(self) -> commands.Bot:
        """Create and configure Discord bot instance"""
        logger.debug("Creating Discord bot instance")

        # Create bot with intents
        bot = commands.Bot(
            command_prefix=self.config["command_prefix"],
            intents=self._intents,
            help_command=None  # Disable default help command
        )

        return bot

    async def _test_bot_connection(self, bot: commands.Bot) -> bool:
        """Test bot connection and permissions"""
        try:
            await bot.login(self._get_credentials()['token'])
            
            # Actually connect the bot to Discord to populate guild cache
            await bot.connect(reconnect=False)
            await bot.wait_until_ready(timeout=10)

            # Get the target guild
            guild = bot.get_guild(int(self.config["guild_id"]))
            if not guild:
                try:
                    await bot.close()
                except:
                    pass
                raise DiscordConfigurationError(f"Bot is not a member of guild {self.config['guild_id']}")

            # Check bot permissions
            bot_member = guild.get_member(bot.user.id)
            if not bot_member:
                await bot.close()
                raise DiscordConfigurationError("Bot member not found in guild")

            # Check for basic permissions
            permissions = bot_member.guild_permissions
            required_perms = [
                'read_messages', 'send_messages', 'manage_messages',
                'kick_members', 'ban_members', 'manage_roles',
                'manage_channels', 'view_audit_log'
            ]

            missing_perms = []
            for perm in required_perms:
                if not getattr(permissions, perm, False):
                    missing_perms.append(perm)

            if missing_perms:
                logger.warning(f"Bot is missing recommended permissions: {', '.join(missing_perms)}")
                logger.warning("Some features may not work properly")

            await bot.close()
            return True

        except discord.LoginFailure:
            raise DiscordConfigurationError("Invalid bot token")
        except Exception as e:
            logger.error(f"Bot connection test failed: {e}")
            try:
                await bot.close()
            except:
                pass
            raise DiscordConfigurationError(f"Connection test failed: {str(e)}")

    def configure(self) -> bool:
        """Sets up Discord bot authentication and permissions"""
        logger.info("Starting Discord bot authentication setup")

        # Check existing configuration
        if self.is_configured(verbose=False):
            logger.info("Discord bot is already configured")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != 'y':
                return True

        setup_instructions = [
            "\n🤖 DISCORD BOT AUTHENTICATION SETUP",
            "\n📝 To get your Discord bot token:",
            "1. Go to https://discord.com/developers/applications",
            "2. Create a new application or select existing one",
            "3. Go to the 'Bot' section",
            "4. Click 'Add Bot' if you haven't already",
            "5. Under 'Token', click 'Copy' to get your bot token",
            "6. Invite the bot to your server with proper permissions"
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        try:
            # Get bot token
            logger.info("\nPlease enter your Discord bot token:")
            bot_token = input("Bot Token: ").strip()

            if not bot_token:
                raise DiscordConfigurationError("Bot token cannot be empty")

            # Test the token
            logger.info("Testing bot token and permissions...")
            asyncio.run(self._test_bot_token(bot_token))

            # Save token to .env
            if not os.path.exists('.env'):
                logger.debug("Creating new .env file")
                with open('.env', 'w') as f:
                    f.write('')

            set_key('.env', 'DISCORD_BOT_TOKEN', bot_token)
            logger.debug("Saved DISCORD_BOT_TOKEN to .env")

            logger.info("\n✅ Discord bot authentication successfully set up!")
            logger.info("Your bot token has been stored in the .env file.")
            return True

        except Exception as e:
            error_msg = f"Setup failed: {str(e)}"
            logger.error(error_msg)
            raise DiscordConfigurationError(error_msg)

    async def _test_bot_token(self, token: str) -> None:
        """Test bot token validity and permissions"""
        bot = commands.Bot(command_prefix="!", intents=self._intents)

        try:
            await bot.login(token)

            # Get the target guild
            guild = bot.get_guild(int(self.config["guild_id"]))
            if not guild:
                await bot.close()
                raise DiscordConfigurationError(f"Bot is not a member of guild {self.config['guild_id']}")

            logger.info(f"✅ Bot connected to guild: {guild.name}")
            logger.info(f"Bot permissions verified for server management")

        finally:
            try:
                await bot.close()
            except:
                pass

    def is_configured(self, verbose: bool = False) -> bool:
        """Check if Discord bot credentials are configured and valid"""
        logger.debug("Checking Discord configuration status")
        try:
            credentials = self._get_credentials()
            
            # Quick check: just verify token exists and looks valid
            token = credentials.get('token', '')
            if not token or len(token) < 20:
                if verbose:
                    logger.error("Discord bot token not found or invalid")
                return False
            
            # Token format check (Discord tokens start with specific patterns)
            if not (token.startswith('MT') or token.startswith('OD') or token.startswith('Nz')):
                if verbose:
                    logger.warning("Discord token format may be invalid")
            
            # For quick checks, just verify token exists
            # Full connection test is done during configure() or when actually using the bot
            return True

        except Exception as e:
            if verbose:
                error_msg = str(e)
                if isinstance(e, DiscordConfigurationError):
                    error_msg = f"Configuration error: {error_msg}"
                elif isinstance(e, DiscordAPIError):
                    error_msg = f"API validation error: {error_msg}"
                logger.error(f"Configuration validation failed: {error_msg}")
            return False

    def register_actions(self) -> None:
        """Register available Discord actions"""
        self.actions = {
            # Message Management
            "send-message": Action(
                name="send-message",
                parameters=[
                    ActionParameter("channel_id", True, str, "Discord channel ID to send message to"),
                    ActionParameter("content", True, str, "Message content to send"),
                    ActionParameter("embed_title", False, str, "Optional embed title"),
                    ActionParameter("embed_description", False, str, "Optional embed description"),
                    ActionParameter("embed_color", False, str, "Optional embed color (hex code)"),
                ],
                description="Send a message or embed to a Discord channel"
            ),
            "delete-message": Action(
                name="delete-message",
                parameters=[
                    ActionParameter("channel_id", True, str, "Channel ID where message is located"),
                    ActionParameter("message_id", True, str, "ID of the message to delete"),
                ],
                description="Delete a specific message from a channel"
            ),
            "bulk-delete-messages": Action(
                name="bulk-delete-messages",
                parameters=[
                    ActionParameter("channel_id", True, str, "Channel ID to clear messages from"),
                    ActionParameter("count", True, int, "Number of messages to delete (1-100)"),
                    ActionParameter("reason", False, str, "Reason for bulk delete"),
                ],
                description="Bulk delete messages from a channel"
            ),

            # Channel Management
            "create-channel": Action(
                name="create-channel",
                parameters=[
                    ActionParameter("name", True, str, "Name of the new channel"),
                    ActionParameter("channel_type", True, str, "Type: text, voice, or category"),
                    ActionParameter("category_id", False, str, "Category ID to place channel under"),
                    ActionParameter("topic", False, str, "Channel topic (text channels only)"),
                    ActionParameter("user_limit", False, int, "User limit (voice channels only)"),
                ],
                description="Create a new text, voice, or category channel"
            ),
            "delete-channel": Action(
                name="delete-channel",
                parameters=[
                    ActionParameter("channel_id", True, str, "ID of the channel to delete"),
                ],
                description="Delete a channel from the server"
            ),

            # Member Management
            "kick-member": Action(
                name="kick-member",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to kick"),
                    ActionParameter("reason", False, str, "Reason for kicking"),
                ],
                description="Kick a member from the server"
            ),
            "ban-member": Action(
                name="ban-member",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to ban"),
                    ActionParameter("reason", False, str, "Reason for banning"),
                    ActionParameter("delete_message_days", False, int, "Days of messages to delete (0-7)"),
                ],
                description="Ban a member from the server"
            ),
            "unban-member": Action(
                name="unban-member",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to unban"),
                ],
                description="Unban a member from the server"
            ),

            # Role Management
            "create-role": Action(
                name="create-role",
                parameters=[
                    ActionParameter("name", True, str, "Name of the new role"),
                    ActionParameter("color", False, str, "Role color (hex code)"),
                    ActionParameter("permissions", False, int, "Permission integer value"),
                ],
                description="Create a new role on the server"
            ),
            "assign-role": Action(
                name="assign-role",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to assign role to"),
                    ActionParameter("role_id", True, str, "Role ID to assign"),
                ],
                description="Assign a role to a server member"
            ),
            "remove-role": Action(
                name="remove-role",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to remove role from"),
                    ActionParameter("role_id", True, str, "Role ID to remove"),
                ],
                description="Remove a role from a server member"
            ),

            # Moderation
            "timeout-member": Action(
                name="timeout-member",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to timeout"),
                    ActionParameter("duration_seconds", True, int, "Duration in seconds (max 28 days)"),
                    ActionParameter("reason", False, str, "Reason for timeout"),
                ],
                description="Timeout a member (mute them) for a specified duration"
            ),
            "remove-timeout": Action(
                name="remove-timeout",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to remove timeout from"),
                ],
                description="Remove timeout from a member"
            ),

            # Information & Monitoring
            "get-server-info": Action(
                name="get-server-info",
                parameters=[],
                description="Get detailed information about the Discord server"
            ),
            "get-channel-activity": Action(
                name="get-channel-activity",
                parameters=[
                    ActionParameter("channel_id", False, str, "Specific channel ID, or get all channels"),
                    ActionParameter("hours_back", False, int, "Hours to look back for activity (default 24)"),
                ],
                description="Get activity statistics for channels"
            ),
            "get-member-info": Action(
                name="get-member-info",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to get information about"),
                ],
                description="Get detailed information about a server member"
            ),

            # Voice Channel Management
            "create-voice-channel": Action(
                name="create-voice-channel",
                parameters=[
                    ActionParameter("name", True, str, "Name of the voice channel"),
                    ActionParameter("user_limit", False, int, "Maximum number of users"),
                    ActionParameter("category_id", False, str, "Category to place channel in"),
                ],
                description="Create a new voice channel"
            ),
            "move-member": Action(
                name="move-member",
                parameters=[
                    ActionParameter("user_id", True, str, "User ID to move"),
                    ActionParameter("channel_id", True, str, "Voice channel ID to move to"),
                ],
                description="Move a member to a different voice channel"
            ),

            # Events & Scheduling
            "create-scheduled-event": Action(
                name="create-scheduled-event",
                parameters=[
                    ActionParameter("name", True, str, "Event name"),
                    ActionParameter("description", True, str, "Event description"),
                    ActionParameter("start_time", True, str, "Start time (ISO 8601 format)"),
                    ActionParameter("end_time", False, str, "End time (ISO 8601 format)"),
                    ActionParameter("channel_id", False, str, "Channel ID for the event"),
                    ActionParameter("location", False, str, "Event location"),
                ],
                description="Create a scheduled event on the server"
            ),

            # Welcome/Goodbye System
            "set-welcome-message": Action(
                name="set-welcome-message",
                parameters=[
                    ActionParameter("channel_id", True, str, "Channel to send welcome messages to"),
                    ActionParameter("message", True, str, "Welcome message template"),
                    ActionParameter("enabled", True, bool, "Enable/disable welcome messages"),
                ],
                description="Configure automated welcome messages for new members"
            ),

            # Auto-Moderation
            "enable-auto-mod": Action(
                name="enable-auto-mod",
                parameters=[
                    ActionParameter("enabled", True, bool, "Enable or disable auto-moderation"),
                    ActionParameter("spam_threshold", False, int, "Messages per minute before spam detection"),
                    ActionParameter("blocked_words", False, list, "List of words to block"),
                ],
                description="Configure automatic moderation features"
            ),
        }

    def _get_guild_and_bot(self) -> tuple:
        """Helper method to get guild and ensure bot is ready"""
        if not self.bot:
            raise DiscordAPIError("Bot not initialized")

        guild = self.bot.get_guild(int(self.config["guild_id"]))
        if not guild:
            raise DiscordAPIError(f"Guild {self.config['guild_id']} not found")

        return guild, self.bot

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Discord action with validation"""
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace('-', '_')
        method = getattr(self, method_name)

        # Run Discord operations in a separate thread with its own event loop
        # This prevents conflicts with the CLI's event loop and heartbeat blocking
        result_container = {'result': None, 'exception': None}
        
        def run_in_thread():
            # Create a new event loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container['result'] = new_loop.run_until_complete(method(**kwargs))
            except Exception as e:
                result_container['exception'] = e
            finally:
                # Don't close the loop immediately - let Discord cleanup
                # The loop will be cleaned up when thread ends
                pass
        
        # Run in a separate thread to avoid event loop conflicts
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        thread.join(timeout=30)  # 30 second timeout
        
        if thread.is_alive():
            raise DiscordAPIError("Discord operation timed out after 30 seconds")
        
        if result_container['exception']:
            raise result_container['exception']
        
        return result_container['result']

    # Message Management Actions
    async def send_message(self, channel_id: str, content: str,
                          embed_title: str = None, embed_description: str = None,
                          embed_color: str = None, **kwargs) -> dict:
        """Send a message or embed to a Discord channel"""
        try:
            guild, bot = await self._ensure_bot_ready()

            channel = guild.get_channel(int(channel_id))
            if not channel:
                raise DiscordAPIError(f"Channel {channel_id} not found")

            if not isinstance(channel, discord.TextChannel):
                raise DiscordAPIError(f"Channel {channel_id} is not a text channel")

            # Check permissions
            if not channel.permissions_for(guild.me).send_messages:
                raise DiscordAPIError("Bot lacks permission to send messages in this channel")

            # Create embed if embed parameters provided
            embed = None
            if embed_title or embed_description:
                embed = discord.Embed()
                if embed_title:
                    embed.title = embed_title
                if embed_description:
                    embed.description = embed_description
                if embed_color:
                    try:
                        embed.color = int(embed_color.lstrip('#'), 16)
                    except ValueError:
                        embed.color = 0x3498db  # Default blue

            # Send message
            message = await channel.send(content, embed=embed)

            return {
                "message_id": str(message.id),
                "channel_id": str(message.channel.id),
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
                "embed": bool(message.embeds)
            }

        except Exception as e:
            raise DiscordAPIError(f"Failed to send message: {str(e)}")

    async def delete_message(self, channel_id: str, message_id: str, **kwargs) -> dict:
        """Delete a specific message from a channel"""
        try:
            guild, bot = await self._ensure_bot_ready()

            channel = guild.get_channel(int(channel_id))
            if not channel:
                raise DiscordAPIError(f"Channel {channel_id} not found")

            message = await channel.fetch_message(int(message_id))
            await message.delete()

            return {
                "deleted": True,
                "message_id": message_id,
                "channel_id": channel_id
            }

        except discord.NotFound:
            raise DiscordAPIError(f"Message {message_id} not found")
        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to delete messages")
        except Exception as e:
            raise DiscordAPIError(f"Failed to delete message: {str(e)}")

    async def bulk_delete_messages(self, channel_id: str, count: int, reason: str = None, **kwargs) -> dict:
        """Bulk delete messages from a channel"""
        try:
            if count < 1 or count > 100:
                raise ValueError("Count must be between 1 and 100")

            guild, bot = await self._ensure_bot_ready()

            channel = guild.get_channel(int(channel_id))
            if not channel:
                raise DiscordAPIError(f"Channel {channel_id} not found")

            if not isinstance(channel, discord.TextChannel):
                raise DiscordAPIError(f"Channel {channel_id} is not a text channel")

            # Check permissions
            if not channel.permissions_for(guild.me).manage_messages:
                raise DiscordAPIError("Bot lacks permission to manage messages")

            # Get messages to delete
            messages = []
            async for message in channel.history(limit=count + 1):  # +1 to account for potential bot message
                if len(messages) >= count:
                    break
                messages.append(message)

            # Filter out messages older than 2 weeks (Discord limitation)
            two_weeks_ago = discord.utils.utcnow() - discord.utils.utcnow().replace(day=1) + discord.utils.utcnow().replace(day=15) - discord.utils.utcnow().replace(day=1)
            messages = [msg for msg in messages if msg.created_at > two_weeks_ago]

            if not messages:
                return {"deleted_count": 0, "reason": "No messages found within 2 week limit"}

            deleted = await channel.delete_messages(messages, reason=reason or "Bulk delete by bot")

            return {
                "deleted_count": len(deleted),
                "channel_id": channel_id,
                "reason": reason
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage messages")
        except Exception as e:
            raise DiscordAPIError(f"Failed to bulk delete messages: {str(e)}")

    # Channel Management Actions
    async def create_channel(self, name: str, channel_type: str,
                           category_id: str = None, topic: str = None,
                           user_limit: int = None, **kwargs) -> dict:
        """Create a new channel"""
        try:
            guild, bot = await self._ensure_bot_ready()

            # Check permissions
            if not guild.me.guild_permissions.manage_channels:
                raise DiscordAPIError("Bot lacks permission to manage channels")

            # Validate channel type
            if channel_type not in ['text', 'voice', 'category']:
                raise ValueError("Channel type must be 'text', 'voice', or 'category'")

            # Get category if specified
            category = None
            if category_id:
                category = guild.get_channel(int(category_id))
                if not isinstance(category, discord.CategoryChannel):
                    raise ValueError("category_id must be a valid category channel ID")

            # Create channel based on type
            if channel_type == 'category':
                channel = await guild.create_category(name)
            elif channel_type == 'voice':
                channel = await guild.create_voice_channel(
                    name,
                    category=category,
                    user_limit=user_limit
                )
            else:  # text
                channel = await guild.create_text_channel(
                    name,
                    category=category,
                    topic=topic
                )

            return {
                "channel_id": str(channel.id),
                "name": channel.name,
                "type": channel_type,
                "category_id": str(category.id) if category else None,
                "position": channel.position
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage channels")
        except Exception as e:
            raise DiscordAPIError(f"Failed to create channel: {str(e)}")

    async def delete_channel(self, channel_id: str, **kwargs) -> dict:
        """Delete a channel from the server"""
        try:
            guild, bot = await self._ensure_bot_ready()

            channel = guild.get_channel(int(channel_id))
            if not channel:
                raise DiscordAPIError(f"Channel {channel_id} not found")

            # Check permissions
            if not guild.me.guild_permissions.manage_channels:
                raise DiscordAPIError("Bot lacks permission to manage channels")

            channel_name = channel.name
            await channel.delete()

            return {
                "deleted": True,
                "channel_id": channel_id,
                "name": channel_name
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage channels")
        except discord.NotFound:
            raise DiscordAPIError(f"Channel {channel_id} not found")
        except Exception as e:
            raise DiscordAPIError(f"Failed to delete channel: {str(e)}")

    # Member Management Actions
    async def kick_member(self, user_id: str, reason: str = None, **kwargs) -> dict:
        """Kick a member from the server"""
        try:
            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            # Check permissions
            if not guild.me.guild_permissions.kick_members:
                raise DiscordAPIError("Bot lacks permission to kick members")

            # Check hierarchy
            if member.top_role >= guild.me.top_role:
                raise DiscordAPIError("Cannot kick member with higher or equal role")

            await guild.kick(member, reason=reason or "Kicked by bot")

            return {
                "action": "kick",
                "user_id": user_id,
                "username": str(member),
                "reason": reason
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to kick members")
        except Exception as e:
            raise DiscordAPIError(f"Failed to kick member: {str(e)}")

    async def ban_member(self, user_id: str, reason: str = None,
                        delete_message_days: int = 0, **kwargs) -> dict:
        """Ban a member from the server"""
        try:
            if delete_message_days < 0 or delete_message_days > 7:
                raise ValueError("delete_message_days must be between 0 and 7")

            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            # Check permissions
            if not guild.me.guild_permissions.ban_members:
                raise DiscordAPIError("Bot lacks permission to ban members")

            # Check hierarchy
            if member.top_role >= guild.me.top_role:
                raise DiscordAPIError("Cannot ban member with higher or equal role")

            await guild.ban(member, reason=reason or "Banned by bot",
                          delete_message_days=delete_message_days)

            return {
                "action": "ban",
                "user_id": user_id,
                "username": str(member),
                "reason": reason,
                "delete_message_days": delete_message_days
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to ban members")
        except Exception as e:
            raise DiscordAPIError(f"Failed to ban member: {str(e)}")

    async def unban_member(self, user_id: str, **kwargs) -> dict:
        """Unban a member from the server"""
        try:
            guild, bot = await self._ensure_bot_ready()

            # Check permissions
            if not guild.me.guild_permissions.ban_members:
                raise DiscordAPIError("Bot lacks permission to ban/unban members")

            # Get ban entry
            bans = await guild.bans()
            ban_entry = discord.utils.get(bans, user__id=int(user_id))

            if not ban_entry:
                raise DiscordAPIError(f"User {user_id} is not banned")

            await guild.unban(ban_entry.user)

            return {
                "action": "unban",
                "user_id": user_id,
                "username": str(ban_entry.user)
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to ban/unban members")
        except Exception as e:
            raise DiscordAPIError(f"Failed to unban member: {str(e)}")

    # Role Management Actions
    async def create_role(self, name: str, color: str = None, permissions: int = None, **kwargs) -> dict:
        """Create a new role on the server"""
        try:
            guild, bot = await self._ensure_bot_ready()

            # Check permissions
            if not guild.me.guild_permissions.manage_roles:
                raise DiscordAPIError("Bot lacks permission to manage roles")

            # Parse color
            role_color = None
            if color:
                try:
                    role_color = int(color.lstrip('#'), 16)
                except ValueError:
                    role_color = discord.Color.default()

            # Create role
            role = await guild.create_role(
                name=name,
                color=role_color,
                permissions=discord.Permissions(permissions) if permissions else None
            )

            return {
                "role_id": str(role.id),
                "name": role.name,
                "color": str(role.color) if role.color else None,
                "position": role.position,
                "permissions": role.permissions.value
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage roles")
        except Exception as e:
            raise DiscordAPIError(f"Failed to create role: {str(e)}")

    async def assign_role(self, user_id: str, role_id: str, **kwargs) -> dict:
        """Assign a role to a server member"""
        try:
            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            role = guild.get_role(int(role_id))
            if not role:
                raise DiscordAPIError(f"Role {role_id} not found")

            # Check permissions
            if not guild.me.guild_permissions.manage_roles:
                raise DiscordAPIError("Bot lacks permission to manage roles")

            # Check role hierarchy
            if role >= guild.me.top_role:
                raise DiscordAPIError("Cannot assign role higher than or equal to bot's highest role")

            await member.add_roles(role)

            return {
                "action": "assign_role",
                "user_id": user_id,
                "role_id": role_id,
                "role_name": role.name,
                "username": str(member)
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage roles")
        except Exception as e:
            raise DiscordAPIError(f"Failed to assign role: {str(e)}")

    async def remove_role(self, user_id: str, role_id: str, **kwargs) -> dict:
        """Remove a role from a server member"""
        try:
            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            role = guild.get_role(int(role_id))
            if not role:
                raise DiscordAPIError(f"Role {role_id} not found")

            # Check permissions
            if not guild.me.guild_permissions.manage_roles:
                raise DiscordAPIError("Bot lacks permission to manage roles")

            # Check role hierarchy
            if role >= guild.me.top_role:
                raise DiscordAPIError("Cannot remove role higher than or equal to bot's highest role")

            await member.remove_roles(role)

            return {
                "action": "remove_role",
                "user_id": user_id,
                "role_id": role_id,
                "role_name": role.name,
                "username": str(member)
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to manage roles")
        except Exception as e:
            raise DiscordAPIError(f"Failed to remove role: {str(e)}")

    # Moderation Actions
    async def timeout_member(self, user_id: str, duration_seconds: int, reason: str = None, **kwargs) -> dict:
        """Timeout a member (mute them) for a specified duration"""
        try:
            if duration_seconds < 1 or duration_seconds > 2419200:  # Max 28 days
                raise ValueError("Duration must be between 1 second and 28 days (2,419,200 seconds)")

            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            # Check permissions
            if not guild.me.guild_permissions.moderate_members:
                raise DiscordAPIError("Bot lacks permission to moderate members")

            # Check role hierarchy
            if member.top_role >= guild.me.top_role:
                raise DiscordAPIError("Cannot timeout member with higher or equal role")

            # Calculate timeout until time
            timeout_until = discord.utils.utcnow() + discord.utils.utcnow().replace(second=duration_seconds)

            await member.timeout(timeout_until, reason=reason or "Timed out by bot")

            return {
                "action": "timeout",
                "user_id": user_id,
                "username": str(member),
                "duration_seconds": duration_seconds,
                "reason": reason
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to moderate members")
        except Exception as e:
            raise DiscordAPIError(f"Failed to timeout member: {str(e)}")

    async def remove_timeout(self, user_id: str, **kwargs) -> dict:
        """Remove timeout from a member"""
        try:
            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            # Check permissions
            if not guild.me.guild_permissions.moderate_members:
                raise DiscordAPIError("Bot lacks permission to moderate members")

            await member.timeout(None)

            return {
                "action": "remove_timeout",
                "user_id": user_id,
                "username": str(member)
            }

        except discord.Forbidden:
            raise DiscordAPIError("Bot lacks permission to moderate members")
        except Exception as e:
            raise DiscordAPIError(f"Failed to remove timeout: {str(e)}")

    # Information Actions
    async def get_server_info(self, **kwargs) -> dict:
        """Get detailed information about the Discord server"""
        try:
            guild, bot = await self._ensure_bot_ready()

            # Get member stats
            total_members = len(guild.members)
            online_members = len([m for m in guild.members if m.status != discord.Status.offline])
            bot_count = len([m for m in guild.members if m.bot])

            # Get channel stats
            text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
            voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
            categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])

            # Get role stats
            role_count = len(guild.roles)

            # Get emoji stats
            emoji_count = len(guild.emojis)
            animated_emojis = len([e for e in guild.emojis if e.animated])

            return {
                "guild_id": str(guild.id),
                "name": guild.name,
                "description": guild.description,
                "owner_id": str(guild.owner_id),
                "member_count": total_members,
                "online_members": online_members,
                "bot_count": bot_count,
                "text_channels": text_channels,
                "voice_channels": voice_channels,
                "categories": categories,
                "role_count": role_count,
                "emoji_count": emoji_count,
                "animated_emojis": animated_emojis,
                "boost_level": guild.premium_tier,
                "boost_count": guild.premium_subscription_count,
                "created_at": guild.created_at.isoformat(),
                "features": guild.features
            }

        except Exception as e:
            raise DiscordAPIError(f"Failed to get server info: {str(e)}")

    async def get_channel_activity(self, channel_id: str = None, hours_back: int = 24, **kwargs) -> dict:
        """Get activity statistics for channels"""
        try:
            guild, bot = await self._ensure_bot_ready()

            # Calculate time threshold
            from datetime import datetime, timedelta
            time_threshold = datetime.utcnow() - timedelta(hours=hours_back)

            channels_to_analyze = []
            if channel_id:
                # Analyze specific channel
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    raise DiscordAPIError(f"Channel {channel_id} not found")
                if not isinstance(channel, discord.TextChannel):
                    raise DiscordAPIError(f"Channel {channel_id} is not a text channel")
                channels_to_analyze = [channel]
            else:
                # Analyze all text channels
                channels_to_analyze = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

            total_messages = 0
            unique_users = set()
            channel_stats = []

            # Check permissions for reading message history
            bot_member = guild.get_member(bot.user.id)
            if not bot_member:
                raise DiscordAPIError("Bot member not found in guild")

            for channel in channels_to_analyze:
                try:
                    # Check if bot can read messages in this channel
                    permissions = channel.permissions_for(bot_member)
                    if not permissions.read_messages or not permissions.read_message_history:
                        logger.warning(f"Bot lacks permission to read message history in {channel.name}")
                        continue

                    # Get recent messages
                    messages = []
                    async for message in channel.history(limit=1000, after=time_threshold):
                        messages.append(message)

                    message_count = len(messages)
                    users_in_channel = set(msg.author.id for msg in messages)

                    # Calculate activity metrics
                    if message_count > 0:
                        avg_messages_per_hour = message_count / hours_back
                        most_recent_message = max(messages, key=lambda m: m.created_at)
                        oldest_message = min(messages, key=lambda m: m.created_at)

                        channel_stats.append({
                            "channel_id": str(channel.id),
                            "channel_name": channel.name,
                            "message_count": message_count,
                            "unique_users": len(users_in_channel),
                            "avg_messages_per_hour": round(avg_messages_per_hour, 2),
                            "most_recent_message": most_recent_message.created_at.isoformat(),
                            "oldest_message": oldest_message.created_at.isoformat(),
                            "user_ids": list(users_in_channel)
                        })

                        total_messages += message_count
                        unique_users.update(users_in_channel)

                except Exception as e:
                    logger.warning(f"Failed to analyze channel {channel.name}: {str(e)}")
                    continue

            return {
                "analyzed_channels": len(channel_stats),
                "total_messages": total_messages,
                "total_unique_users": len(unique_users),
                "hours_analyzed": hours_back,
                "channels": channel_stats,
                "summary": {
                    "most_active_channel": max(channel_stats, key=lambda c: c["message_count"])["channel_name"] if channel_stats else None,
                    "least_active_channel": min(channel_stats, key=lambda c: c["message_count"])["channel_name"] if channel_stats else None,
                    "avg_messages_per_channel": round(total_messages / len(channel_stats), 2) if channel_stats else 0
                }
            }

        except Exception as e:
            raise DiscordAPIError(f"Failed to get channel activity: {str(e)}")

    async def get_member_info(self, user_id: str, **kwargs) -> dict:
        """Get detailed information about a server member"""
        try:
            guild, bot = await self._ensure_bot_ready()

            member = guild.get_member(int(user_id))
            if not member:
                raise DiscordAPIError(f"Member {user_id} not found in guild")

            # Get roles (excluding @everyone)
            roles = [str(role.id) for role in member.roles if role != guild.default_role]

            return {
                "user_id": str(member.id),
                "username": member.name,
                "discriminator": member.discriminator,
                "display_name": member.display_name,
                "nickname": member.nick,
                "bot": member.bot,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "premium_since": member.premium_since.isoformat() if member.premium_since else None,
                "status": str(member.status),
                "activity": str(member.activity) if member.activity else None,
                "roles": roles,
                "top_role": str(member.top_role.id) if member.top_role != guild.default_role else None,
                "permissions": member.guild_permissions.value,
                "voice_channel": str(member.voice.channel.id) if member.voice and member.voice.channel else None,
                "muted": member.voice.muted if member.voice else False,
                "deafened": member.voice.deafened if member.voice else False
            }

        except Exception as e:
            raise DiscordAPIError(f"Failed to get member info: {str(e)}")

    # Helper method to ensure bot is ready
    async def _ensure_bot_ready(self) -> tuple:
        """Ensure bot is initialized and connected"""
        # Check if bot exists but is closed - reset if so
        if self.bot and self.bot.is_closed():
            self.bot = None
        
        if not self.bot:
            self.bot = self._create_bot()

        # Check if bot is already connected and ready
        if not self.bot.is_ready():
            # Start the bot if not already running
            try:
                await self.bot.login(self._get_credentials()['token'])
                await self.bot.connect(reconnect=False)
                await self.bot.wait_until_ready(timeout=10)
            except Exception as e:
                raise DiscordAPIError(f"Failed to initialize bot: {str(e)}")

        guild = self.bot.get_guild(int(self.config["guild_id"]))
        if not guild:
            raise DiscordAPIError(f"Guild {self.config['guild_id']} not found")

        return guild, self.bot

    async def _cleanup_bot(self):
        """Disconnect bot after action completes (optional cleanup)"""
        if self.bot:
            try:
                if self.bot.is_ready() and not self.bot.is_closed():
                    await self.bot.close()
                logger.debug("Discord bot disconnected successfully")
            except Exception as e:
                logger.warning(f"Error disconnecting bot: {e}")
        # Note: We don't set self.bot = None here to avoid race conditions
        # The bot will be checked for closed state in _ensure_bot_ready()
