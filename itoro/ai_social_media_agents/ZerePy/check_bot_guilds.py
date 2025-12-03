#!/usr/bin/env python3
"""
Check what Discord guilds (servers) the bot is currently a member of
"""
import os
import discord
from discord.ext import commands

# Set token directly
DISCORD_BOT_TOKEN = "MTQ0NTU3MDA1ODQ0MDAyMDA0OA.Gjj3B3.wv4P-RCBRTGguRQrv7xoTRYkjB3OE0I378rVg8"

async def check_guilds():
    """Check what guilds the bot is in"""
    print("🤖 Checking Discord Bot Guild Membership")
    print("=" * 50)

    # Create bot with minimal intents
    intents = discord.Intents.default()
    intents.guilds = True

    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

    try:
        await bot.login(DISCORD_BOT_TOKEN)
        print("✅ Bot token is valid")

        # Get guilds
        await bot.connect(reconnect=False)
        await bot.wait_until_ready()

        print(f"\n📋 Bot is a member of {len(bot.guilds)} server(s):")
        for guild in bot.guilds:
            print(f"  - {guild.name} (ID: {guild.id})")

        # Check for the specific guild
        target_guild_id = 1445575379321360527
        target_guild = bot.get_guild(target_guild_id)
        if target_guild:
            print(f"\n✅ Bot IS a member of target guild: {target_guild.name}")
            print(f"   Guild ID: {target_guild.id}")
            print(f"   Member count: {target_guild.member_count}")

            # Check bot permissions
            bot_member = target_guild.get_member(bot.user.id)
            if bot_member:
                permissions = bot_member.guild_permissions
                print(f"   Bot permissions: {permissions}")
        else:
            print(f"\n❌ Bot is NOT a member of target guild (ID: {target_guild_id})")

    except discord.LoginFailure:
        print("❌ Invalid bot token")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            await bot.close()
        except:
            pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_guilds())
