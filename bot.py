#!/bin/python3
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variable
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Create a bot instance with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
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

# Run the bot
if __name__ == '__main__':
    bot.run(TOKEN)