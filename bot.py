#!/usr/bin/env python3
import os
import json
import datetime
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variable
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

with open('config.json') as f:
    config = json.load(f)

GUILD_ID           = config['guild_id']
CATEGORY_ID        = config['thursday_category_id']
THURSDAY_CHANNEL   = "the-final-thursday"  # Will be overridable via db.json later

CENTRAL = ZoneInfo("America/Chicago")
MIDNIGHT = datetime.time(0, 0, 0, tzinfo=CENTRAL)

# Create a bot instance with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    await bot.tree.sync()  # Registers slash commands with Discord
    thursday_open.start()
    print(f'{bot.user} is online!')


@bot.event
async def on_member_join(member: discord.Member):
    try:
        await member.edit(nick="Thursday")
        print(f"Renamed {member.name} to Thursday.")
    except discord.Forbidden:
        # Bot's role is too low or this is somehow the server owner
        print(f"Could not rename {member.name}: missing permissions or they outrank me")
    except discord.HTTPException as e:
        # Other error
        print(f"Could not rename {member.name}: {e}")


@tasks.loop(time=MIDNIGHT)
async def thursday_open():
    # tasks fires every day at midnight Central; skip non-Thursdays
    if datetime.datetime.now(CENTRAL).weekday() != 3:  # 0=Mon, 3=Thu, 4=Fri
        return

    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        print("thursday_open: guild not found")
        return

    category = guild.get_channel(int(CATEGORY_ID))
    if not category or not isinstance(category, discord.CategoryChannel):
        print("thursday_open: category not found")
        return

    # @everyone can read, send messages, and add reactions; nothing else by default
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            add_reactions=True,
            read_message_history=True,
        )
    }

    try:
        channel = await guild.create_text_channel(
            name=THURSDAY_CHANNEL,
            category=category,
            overwrites=overwrites,
            reason=f"Thursday auto-open",
        )
        await channel.edit(position=0)
        await channel.send("@everyone it's Thursday!")
        print(f"Opened #{channel.name}")
    except discord.Forbidden:
        print("thursday_open: missing Manage Channels permission")
    except discord.HTTPException as e:
        print(f"thursday_open: failed to create channel: {e}")


# Run the bot
if __name__ == '__main__':
    bot.run(TOKEN)