#!/usr/bin/env python3
import os
import json
import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the bot token from environment variable
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

with open('config.json') as f:
    config = json.load(f)

GUILD_ID         = config['guild_id']
FIRST_THURSDAY   = datetime.date.fromisoformat(config['first_thursday'])
THURSDAY_CHANNEL = "the-final-thursday"  # Will be overridable via db.json later

CENTRAL  = ZoneInfo("America/Chicago")
MIDNIGHT = datetime.time(0, 0, 0, tzinfo=CENTRAL)

# Max Thursday channels before a first-half category overflows into the second half category
CHANNELS_PER_HALF = 26

# Create a bot instance with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


# db.json helpers

DB_PATH = Path('db.json')


def load_db() -> dict:
    """Read and return the full db.json contents as a dict."""
    if not DB_PATH.exists():
        return {}
    text = DB_PATH.read_text().strip()
    return json.loads(text) if text else {}


def save_db(data: dict) -> None:
    """Write *data* back to db.json (pretty-printed)."""
    DB_PATH.write_text(json.dumps(data, indent=2))


def get_thursday_only_channels(guild_id: int) -> list[int]:
    """Return the list of Thursday-only channel IDs for a guild."""
    db = load_db()
    return db.get(str(guild_id), {}).get("thursday_only_channels", [])


def add_thursday_only_channel(guild_id: int, channel_id: int) -> bool:
    """Append *channel_id* to the guild's Thursday-only list.

    Returns True if the channel was newly added, False if it was already present.
    """
    db = load_db()
    key = str(guild_id)
    guild_data = db.setdefault(key, {})
    channels: list[int] = guild_data.setdefault("thursday_only_channels", [])
    if channel_id in channels:
        return False
    channels.append(channel_id)
    save_db(db)
    return True


def remove_thursday_only_channel(guild_id: int, channel_id: int) -> bool:
    """Remove *channel_id* from the guild's Thursday-only list.

    Returns True if the channel was removed, False if it wasn't in the list.
    """
    db = load_db()
    key = str(guild_id)
    channels: list[int] = db.get(key, {}).get("thursday_only_channels", [])
    if channel_id not in channels:
        return False
    channels.remove(channel_id)
    db[key]["thursday_only_channels"] = channels
    save_db(db)
    return True


# helper functions

def get_thursday_year_and_half(date: datetime.date) -> tuple[int, int]:
    """Return (year_number, half) for the given date.

    year_number is 1-indexed, starting at 1 for the calendar year in which the
    first Thursday occurred (e.g. 2019 -> 1, 2020 -> 2, ect., ... 2026 -> 8).
    half is 1 for January–June and 2 for July–December.
    """
    year_num = date.year - FIRST_THURSDAY.year + 1
    half = 1 if date.month <= 6 else 2
    return year_num, half


def thursday_category_name(year_num: int, half: int) -> str:
    """Build the canonical category name for the given year/half period.

    Example: thursday_category_name(8, 1) -> 'THURSDAY YEAR 8 (1/2)'
    """
    return f"THURSDAY YEAR {year_num} ({half}/2)"


def count_thursdays_so_far(as_of_date: datetime.date | None = None) -> int:
    """Count Thursdays from (and including) the very first Thursday up to as_of_date.

    Returns 0 if as_of_date is before the first Thursday.
    """
    if as_of_date is None:
        as_of_date = datetime.datetime.now(CENTRAL).date()
    if as_of_date < FIRST_THURSDAY:
        return 0
    return (as_of_date - FIRST_THURSDAY).days // 7 + 1


def find_thursday_category(
    guild: discord.Guild, year_num: int, half: int
) -> discord.CategoryChannel | None:
    """Look up a Thursday year category in the guild by its canonical name."""
    return discord.utils.get(guild.categories, name=thursday_category_name(year_num, half))


def find_latest_thursday_category(guild: discord.Guild) -> discord.CategoryChannel | None:
    """Find the Thursday year category whose name matches today's date period.

    The expected name is derived from the current date relative to the year of
    the first Thursday stored in config.json.  For example, if today falls in
    the first half of year 8, this returns the category named 'THURSDAY YEAR 8 (1/2)'.
    Returns None if that category has not been created yet.
    """
    today = datetime.datetime.now(CENTRAL).date()
    year_num, half = get_thursday_year_and_half(today)
    return find_thursday_category(guild, year_num, half)


def find_previous_thursday_category(
    guild: discord.Guild, year_num: int, half: int
) -> discord.CategoryChannel | None:
    """Return the Thursday year category that immediately precedes the given period.

    For (X, 2): the previous period is (X, 1).
    For (X, 1): try (X-1, 2) first, then fall back to (X-1, 1).
    Returns None if no previous category can be found (e.g. very first category).
    """
    if half == 2:
        return find_thursday_category(guild, year_num, 1)

    # half == 1: look in the previous calendar year
    prev = find_thursday_category(guild, year_num - 1, 2)
    if prev is None:
        prev = find_thursday_category(guild, year_num - 1, 1)
    return prev


async def create_thursday_category(
    guild: discord.Guild,
    year_num: int,
    half: int,
    above: discord.CategoryChannel | None,
) -> discord.CategoryChannel:
    """Create a new Thursday year category and position it directly above `above`.

    If `above` is None the category is simply appended wherever Discord places it.
    Positioning works by first creating the category (Discord appends it at the
    end), then calling edit(position=above.position), which inserts the new
    category at that slot and shifts `above` and everything below it down by one.
    """
    name = thursday_category_name(year_num, half)
    new_cat = await guild.create_category(
        name,
        reason=f"Thursday auto-create: {name}",
    )

    if above is not None:
        # Re-fetch the above category's current position in case it shifted.
        # guild.get_channel returns the cached object with the live position.
        fresh_above = guild.get_channel(above.id)
        target_pos = fresh_above.position if fresh_above else above.position
        await new_cat.edit(position=target_pos)

    print(f"Created category '{name}' at position {new_cat.position}")
    return new_cat


async def get_or_create_target_category(
    guild: discord.Guild, today: datetime.date
) -> discord.CategoryChannel | None:
    """Determine and return the correct Thursday category for today's channel.

    Rules (evaluated in order):
    1. If the expected category for this period doesn't exist yet, create it.
       - First Thursday of a new year  → new (X, 1/2) category above last year's.
       - First Thursday of second half → new (X, 2/2) category above this year's (1/2).
         (This case is also covered by rule 2 on the very day of overflow.)
    2. If the current (1/2) category already holds CHANNELS_PER_HALF channels,
       redirect to the (2/2) category for the same year, creating it if necessary.
    3. Otherwise return the existing category as-is.
    """
    year_num, half = get_thursday_year_and_half(today)
    cat = find_thursday_category(guild, year_num, half)

    if cat is None:
        # Category for this period does not exist yet – create it.
        prev = find_previous_thursday_category(guild, year_num, half)
        cat = await create_thursday_category(guild, year_num, half, prev)
        return cat

    # Category exists.  Check for first-half overflow → redirect to second half.
    if half == 1:
        thursday_channel_count = sum(
            1 for c in cat.channels if isinstance(c, discord.TextChannel)
        )
        if thursday_channel_count >= CHANNELS_PER_HALF:
            cat2 = find_thursday_category(guild, year_num, 2)
            if cat2 is None:
                cat2 = await create_thursday_category(guild, year_num, 2, cat)
            return cat2

    return cat


# Thursday-only channel lock / unlock (all servers)

_LOCKED_PERMS   = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=False,
    read_message_history=True,
)
_UNLOCKED_PERMS = discord.PermissionOverwrite(
    view_channel=True,
    send_messages=True,
    read_message_history=True,
)


async def _apply_thursday_only_perms(locked: bool) -> None:
    """Lock or unlock every Thursday-only channel across all guilds in db.json."""
    db = load_db()
    perms = _LOCKED_PERMS if locked else _UNLOCKED_PERMS
    action = "Locked" if locked else "Unlocked"

    for guild_id_str, guild_data in db.items():
        channel_ids: list[int] = guild_data.get("thursday_only_channels", [])
        if not channel_ids:
            continue

        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            print(f"_apply_thursday_only_perms: guild {guild_id_str} not found")
            continue

        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                print(
                    f"_apply_thursday_only_perms: channel {channel_id} "
                    f"not found in guild {guild_id_str}"
                )
                continue

            overwrites = channel.overwrites
            overwrites[guild.default_role] = perms
            try:
                await channel.edit(overwrites=overwrites)
                print(f"{action} Thursday-only channel #{channel.name} in '{guild.name}'")
            except discord.Forbidden as e:
                print(f"_apply_thursday_only_perms: #{channel.name}: forbidden: {e}")
            except discord.HTTPException as e:
                print(f"_apply_thursday_only_perms: #{channel.name}: {e}")


# bot events

@bot.event
async def on_ready():
    # Create db.json if it doesn't exist
    if not DB_PATH.exists():
        save_db({})
        print('Created db.json')

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


async def thursday_close():
    """Lock the open Thursday channel and rename it with its sequence number."""
    today        = datetime.datetime.now(CENTRAL).date()
    thursday_num = count_thursdays_so_far(today)  # Friday's count == the just-passed Thursday's

    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        print("thursday_close: guild not found")
        return

    channel = discord.utils.get(guild.text_channels, name=THURSDAY_CHANNEL)
    if not channel:
        print(f"thursday_close: #{THURSDAY_CHANNEL} not found")
        return

    # @everyone can only read and react; no sending
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=False,
            read_message_history=True,
        )
    }

    try:
        await channel.send("@everyone Thursday is gone forever.")
        await channel.edit(name=f"thursday-{thursday_num}")
        await channel.edit(overwrites=overwrites)
        print(f"Closed #{channel.name} (Thursday #{thursday_num})")
    except discord.Forbidden as e:
        print(f"thursday_close: {e}")
    except discord.HTTPException as e:
        print(f"thursday_close: failed: {e}")

    # Re-lock all Thursday-only channels across every guild
    await _apply_thursday_only_perms(locked=True)


@tasks.loop(time=MIDNIGHT)
async def thursday_open():
    # Tasks fire every day at midnight Central; handle Thursdays and Fridays
    now     = datetime.datetime.now(CENTRAL)
    weekday = now.weekday()  # 0=Mon, 3=Thu, 4=Fri

    if weekday == 4:  # Friday – close last night's Thursday channel
        await thursday_close()
        return
    elif weekday != 3:  # Not Thursday or Friday – nothing to do
        return

    today        = now.date()
    thursday_num = count_thursdays_so_far(today)

    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        print("thursday_open: guild not found")
        return

    category = await get_or_create_target_category(guild, today)
    if not category:
        print("thursday_open: could not find or create a target category")
        return

    # @everyone can read, send messages, and reactions; nothing else by default
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )
    }

    try:
        channel = await guild.create_text_channel(
            name=THURSDAY_CHANNEL,
            category=category,
            overwrites=overwrites,
            reason="Thursday auto-open",
        )
        await channel.edit(position=0)
        await channel.send("@everyone it's Thursday!")
        print(
            f"Opened #{channel.name} in '{category.name}' "
            f"(Thursday #{thursday_num})"
        )
    except discord.Forbidden as e:
        print(f"thursday_open: {e}")
    except discord.HTTPException as e:
        print(f"thursday_open: failed to create channel: {e}")

    # Unlock all Thursday-only channels across every guild
    await _apply_thursday_only_perms(locked=False)


# Slash commands

@bot.tree.command(
    name="set-thursday-only",
    description="Make a channel read-only for @everyone except on Thursdays.",
)
@app_commands.describe(channel="The channel to restrict to Thursdays only.")
@app_commands.checks.has_permissions(manage_channels=True)
async def set_thursday_only(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
) -> None:
    """Register *channel* as Thursday-only and immediately apply the correct perms."""
    guild = interaction.guild

    # Persist - bail early if already registered
    newly_added = add_thursday_only_channel(guild.id, channel.id)
    if not newly_added:
        await interaction.response.send_message(
            f"{channel.mention} is already set as Thursday-only.",
            ephemeral=True,
        )
        return

    # Apply permissions right now based on the current day
    today      = datetime.datetime.now(CENTRAL)
    is_thursday = today.weekday() == 3
    perms       = _UNLOCKED_PERMS if is_thursday else _LOCKED_PERMS

    overwrites = channel.overwrites
    overwrites[guild.default_role] = perms

    try:
        await channel.edit(overwrites=overwrites)
    except discord.Forbidden:
        # Roll back the db entry so the state stays consistent
        remove_thursday_only_channel(guild.id, channel.id)
        await interaction.response.send_message(
            f"I don't have permission to edit {channel.mention}. "
            "Please check my role's channel permissions and try again.\n"
            "-# Note: I cannot edit permissions I don't have myself.",
            ephemeral=True,
        )
        return
    except discord.HTTPException as e:
        remove_thursday_only_channel(guild.id, channel.id)
        await interaction.response.send_message(
            f"Something went wrong while updating {channel.mention}: `{e}`",
            ephemeral=True,
        )
        return

    status = "unlocked for Thursday" if is_thursday else "locked until Thursday"
    await interaction.response.send_message(
        f"{channel.mention} is now Thursday-only (currently {status}).",
        ephemeral=True,
    )
    print(
        f"set-thursday-only: #{channel.name} in '{guild.name}' "
        f"registered and {'unlocked' if is_thursday else 'locked'} "
        f"by {interaction.user}"
    )


@set_thursday_only.error
async def set_thursday_only_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need the **Manage Channels** permission to use this command.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"An unexpected error occurred: `{error}`",
            ephemeral=True,
        )

# Run the bot
if __name__ == '__main__':
    if not TOKEN:
        print("Please set the DISCORD_BOT_TOKEN environment variable.")
        exit(1)

    bot.run(TOKEN)
