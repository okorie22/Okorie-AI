"""
Discord Bot for SolPattern AI Detector
Handles private DM notifications for pattern alerts
"""

import discord
from discord.ext import commands
import asyncio
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
import threading
import time
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Get app root directory (go up 2 levels from pattern_detection folder)
APP_ROOT = Path(__file__).parent.parent.parent
DISCORD_DB_PATH = APP_ROOT / "data" / "discord_users.db"

class DiscordBot:
    """Discord bot for sending private pattern notifications"""

    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or os.getenv('DISCORD_BOT_TOKEN')
        self.bot = None
        self.user_ids = {}  # Cache of authorized user IDs
        self.running = False
        self.loop = None

        if not self.bot_token:
            print("[DISCORD] Warning: No bot token provided")
            return

        # Initialize bot
        intents = discord.Intents.default()
        intents.message_content = True  # Need this for DM commands

        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.setup_events()
        self.setup_commands()

    def setup_events(self):
        """Setup bot event handlers"""
        @self.bot.event
        async def on_ready():
            print(f'🤖 Discord bot logged in as {self.bot.user}')
            print(f'🤖 Connected to {len(self.bot.guilds)} servers')

        @self.bot.event
        async def on_message(message):
            # Process commands
            await self.bot.process_commands(message)

    def setup_commands(self):
        """Setup bot commands"""

        @self.bot.command(name='enable_alerts')
        async def enable_alerts(ctx):
            """User enables alerts via DM"""
            if ctx.guild:  # Not in DM
                await ctx.send("Please DM me this command to enable private alerts!")
                return

            user_id = str(ctx.author.id)
            username = str(ctx.author)

            # Store user ID for alerts
            self.store_discord_user(user_id, username)

            # Confirm to user
            embed = discord.Embed(
                title="✅ Pattern Alerts Enabled",
                description="You'll now receive SolPattern AI Detector notifications in this DM!",
                color=0x00ff00,
                timestamp=datetime.now()
            )

            embed.add_field(
                name="What you'll receive:",
                value="• Real-time pattern detections\n• AI-powered analysis\n• Trading signals",
                inline=False
            )

            embed.set_footer(text="Use !disable_alerts to stop notifications")

            await ctx.send(embed=embed)
            print(f"[DISCORD] User {username} ({user_id}) enabled alerts")

        @self.bot.command(name='disable_alerts')
        async def disable_alerts(ctx):
            """User disables alerts"""
            if ctx.guild:  # Not in DM
                await ctx.send("Please DM me this command to disable alerts!")
                return

            user_id = str(ctx.author.id)
            username = str(ctx.author)

            # Remove user ID
            self.remove_discord_user(user_id)

            embed = discord.Embed(
                title="❌ Pattern Alerts Disabled",
                description="You will no longer receive notifications.",
                color=0xff0000,
                timestamp=datetime.now()
            )

            embed.set_footer(text="Use !enable_alerts to re-enable")

            await ctx.send(embed=embed)
            print(f"[DISCORD] User {username} ({user_id}) disabled alerts")

        @self.bot.command(name='status')
        async def status(ctx):
            """Check alert status"""
            if ctx.guild:
                await ctx.send("Please DM me for status information!")
                return

            user_id = str(ctx.author.id)
            enabled = self.is_user_enabled(user_id)

            embed = discord.Embed(
                title="📊 Alert Status",
                color=0x00ff00 if enabled else 0xff0000,
                timestamp=datetime.now()
            )

            embed.add_field(
                name="Status",
                value="✅ Enabled" if enabled else "❌ Disabled",
                inline=True
            )

            embed.add_field(
                name="Bot",
                value="🟢 Online",
                inline=True
            )

            if enabled:
                embed.set_footer(text="Receiving pattern alerts • Use !disable_alerts to stop")
            else:
                embed.set_footer(text="Not receiving alerts • Use !enable_alerts to start")

            await ctx.send(embed=embed)

        @self.bot.command(name='info')
        async def info_cmd(ctx):
            """Show bot information"""
            embed = discord.Embed(
                title="SolPattern AI Detector Bot",
                description="Get real-time crypto pattern alerts with AI analysis",
                color=0x0099ff
            )

            embed.add_field(
                name="!enable_alerts",
                value="Enable private pattern notifications",
                inline=False
            )

            embed.add_field(
                name="!disable_alerts",
                value="Disable pattern notifications",
                inline=False
            )

            embed.add_field(
                name="!status",
                value="Check your alert status",
                inline=False
            )

            embed.set_footer(text="DM me these commands for setup")

            await ctx.send(embed=embed)

    def store_discord_user(self, discord_user_id: str, username: str):
        """Store Discord user ID in database"""
        try:
            with sqlite3.connect(str(DISCORD_DB_PATH)) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS discord_users (
                        discord_user_id TEXT PRIMARY KEY,
                        username TEXT,
                        enabled BOOLEAN DEFAULT 1,
                        created_at TEXT,
                        updated_at TEXT
                    )
                ''')

                conn.execute('''
                    INSERT OR REPLACE INTO discord_users
                    (discord_user_id, username, enabled, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                ''', (
                    discord_user_id,
                    username,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                print(f"[DISCORD] Stored user {username} ({discord_user_id})")

        except Exception as e:
            print(f"[DISCORD] Error storing user {discord_user_id}: {e}")

    def remove_discord_user(self, discord_user_id: str):
        """Remove Discord user from database"""
        try:
            with sqlite3.connect(str(DISCORD_DB_PATH)) as conn:
                conn.execute(
                    'UPDATE discord_users SET enabled = 0, updated_at = ? WHERE discord_user_id = ?',
                    (datetime.now().isoformat(), discord_user_id)
                )
                print(f"[DISCORD] Disabled alerts for user {discord_user_id}")

        except Exception as e:
            print(f"[DISCORD] Error removing user {discord_user_id}: {e}")

    def is_user_enabled(self, discord_user_id: str) -> bool:
        """Check if user has enabled alerts"""
        try:
            with sqlite3.connect(str(DISCORD_DB_PATH)) as conn:
                cursor = conn.execute(
                    'SELECT enabled FROM discord_users WHERE discord_user_id = ?',
                    (discord_user_id,)
                )
                result = cursor.fetchone()
                return result[0] == 1 if result else False

        except Exception as e:
            print(f"[DISCORD] Error checking user {discord_user_id}: {e}")
            return False

    def get_enabled_users(self) -> list:
        """Get list of users with enabled alerts"""
        try:
            with sqlite3.connect(str(DISCORD_DB_PATH)) as conn:
                cursor = conn.execute(
                    'SELECT discord_user_id, username FROM discord_users WHERE enabled = 1'
                )
                return [(row[0], row[1]) for row in cursor.fetchall()]

        except Exception as e:
            print(f"[DISCORD] Error getting enabled users: {e}")
            return []

    async def send_pattern_alert(self, discord_user_id: str, pattern_data: Dict[str, Any]) -> bool:
        """Send private pattern alert to user"""
        if not self.bot or not self.running:
            print(f"[DISCORD] Bot not running, cannot send alert to {discord_user_id}")
            return False

        try:
            # Check if user has enabled alerts
            if not self.is_user_enabled(discord_user_id):
                print(f"[DISCORD] User {discord_user_id} has disabled alerts")
                return False

            # Get user object
            user = self.bot.get_user(int(discord_user_id))
            if not user:
                # Try to fetch user
                try:
                    user = await self.bot.fetch_user(int(discord_user_id))
                except discord.NotFound:
                    print(f"[DISCORD] User {discord_user_id} not found")
                    return False

            # Create alert embed
            embed = self.create_alert_embed(pattern_data)

            # Send DM
            await user.send(embed=embed)
            print(f"[DISCORD] Alert sent to user {discord_user_id} for {pattern_data.get('symbol', 'Unknown')}")
            return True

        except discord.Forbidden:
            print(f"[DISCORD] Cannot send DM to user {discord_user_id} - DMs disabled")
            # Auto-disable alerts for this user
            self.remove_discord_user(discord_user_id)
            return False

        except Exception as e:
            print(f"[DISCORD] Error sending alert to user {discord_user_id}: {e}")
            return False

    def create_alert_embed(self, pattern_data: Dict[str, Any]) -> discord.Embed:
        """Create rich Discord embed for pattern alert"""
        # Determine color based on direction
        color = 0xff4444 if pattern_data.get('direction') == 'short' else 0x44ff44

        embed = discord.Embed(
            title=f"ALERT: {pattern_data.get('symbol', 'Unknown')} Pattern Detected",
            color=color,
            timestamp=datetime.now()
        )

        # Basic pattern info
        embed.add_field(
            name="Pattern",
            value=pattern_data.get('pattern', 'Unknown').upper(),
            inline=True
        )

        embed.add_field(
            name="Direction",
            value=pattern_data.get('direction', 'Unknown').upper(),
            inline=True
        )

        embed.add_field(
            name="Confidence",
            value=f"{pattern_data.get('confidence', 0):.1%}",
            inline=True
        )

        # Price and market data
        price = pattern_data.get('ohlcv', {}).get('close', pattern_data.get('price', 0))
        if price:
            embed.add_field(
                name="Price",
                value=f"${price:.2f}",
                inline=True
            )

        regime = pattern_data.get('regime', 'Unknown')
        regime_conf = pattern_data.get('regime_confidence', 0)
        embed.add_field(
            name="Market Regime",
            value=f"{regime.replace('_', ' ').title()} ({regime_conf:.0%})",
            inline=True
        )

        # Confirmations
        confirmations = pattern_data.get('confirmations', {})
        conf_text = []
        for key, value in confirmations.items():
            status = "✅" if value else "❌"
            conf_text.append(f"{key.title()}: {status}")

        if conf_text:
            embed.add_field(
                name="Confirmations",
                value="\n".join(conf_text),
                inline=False
            )

        # Parameters (if available)
        params = pattern_data.get('parameters', {})
        if params:
            param_text = []
            if 'stop_loss_pct' in params:
                param_text.append(f"Stop Loss: {params['stop_loss_pct']*100:.1f}%")
            if 'profit_target_pct' in params:
                param_text.append(f"Target: {params['profit_target_pct']*100:.1f}%")
            if 'max_holding_period' in params:
                param_text.append(f"Max Hold: {params['max_holding_period']} bars")

            if param_text:
                embed.add_field(
                    name="Parameters",
                    value="\n".join(param_text),
                    inline=True
                )

        # AI Analysis (truncated for Discord limits)
        ai_analysis = pattern_data.get('ai_analysis', '')
        if ai_analysis:
            # Discord embed field limit is 1024 characters
            if len(ai_analysis) > 1000:
                ai_analysis = ai_analysis[:997] + "..."
            embed.add_field(
                name="AI Analysis",
                value=ai_analysis,
                inline=False
            )

        # Footer
        embed.set_footer(text="SolPattern AI Detector • Real-time Analysis")

        return embed

    async def start_bot_async(self):
        """Start the Discord bot (async)"""
        if not self.bot or not self.bot_token:
            print("[DISCORD] Bot not initialized or no token")
            return

        self.running = True
        try:
            await self.bot.start(self.bot_token)
        except Exception as e:
            print(f"[DISCORD] Error starting bot: {e}")
            self.running = False

    def start_bot_threaded(self):
        """Start bot in background thread"""
        if not self.bot_token:
            return

        def run_bot():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            try:
                self.loop.run_until_complete(self.start_bot_async())
            except Exception as e:
                print(f"[DISCORD] Bot thread error: {e}")
            finally:
                self.running = False

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        print("[DISCORD] Bot started in background thread")

    def stop_bot(self):
        """Stop the Discord bot"""
        if self.bot and self.running:
            async def stop_async():
                await self.bot.close()
                self.running = False

            if self.loop:
                self.loop.create_task(stop_async())
            print("[DISCORD] Bot stop requested")

    def is_running(self) -> bool:
        """Check if bot is running"""
        return self.running and self.bot is not None


# Global bot instance for easy access
_discord_bot_instance = None

def get_discord_bot() -> DiscordBot:
    """Get global Discord bot instance"""
    global _discord_bot_instance
    if _discord_bot_instance is None:
        _discord_bot_instance = DiscordBot()
    return _discord_bot_instance

def start_discord_bot():
    """Start the Discord bot"""
    bot = get_discord_bot()
    bot.start_bot_threaded()

if __name__ == "__main__":
    # Test the bot
    print("🤖 Starting Discord Bot for Testing...")
    bot = DiscordBot()
    bot.start_bot_threaded()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🤖 Stopping Discord Bot...")
        bot.stop_bot()
