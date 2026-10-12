
import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ROSTER_CHANNEL_ID = 1558889366565167284

# Change the embed colour here.
EMBED_COLOUR = 0x5865F2

EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

STATE_FILE = "roster_state.json"
PREFIX = "!"

# ============================================================
# STAFF HIERARCHY — HIGHEST RANK FIRST
# ============================================================

GROUPS = [
    {"name": "Founder", "role_id": 1558896822410547210, "target": 1, "section": "Ownership"},
    {"name": "Owner", "role_id": 1558896894678278164, "target": 2, "section": "Ownership"},
    {"name": "Co Owner", "role_id": 1558896918443327589, "target": None, "section": "Ownership"},

    {"name": "Operations", "role_id": 1558896966459592704, "target": 4, "section": "Leadership"},
    {"name": "Directors", "role_id": 1558897001406406741, "target": 8, "section": "Leadership"},

    {"name": "General Management", "role_id": 1558897060441235558, "target": 4, "section": "Management"},
    {"name": "Management", "role_id": 1558897026568028273, "target": 13, "section": "Management"},
    {"name": "Admin", "role_id": 1558897520606974112, "target": 5, "section": "Management"},

    {"name": "Staff", "role_id": 1558897546242429100, "target": 10, "section": "Staff"},
    {"name": "Trial Staff", "role_id": 1558897577976528957, "target": 10, "section": "Staff"},
]

MANAGEMENT_ROLE_ID = 1558897026568028273

DEPARTMENT_ROLE_IDS = [
    1558897194281467987,
    1558897228666634281,
    1558897253928935435,
    1558897283960148152,
    1558897330374180968,
    1558897439602114607,
    1558897464826798232,
    1558897488151191694,
]

SECTION_ORDER = ["Ownership", "Leadership", "Management", "Staff"]

SECTION_EMOJIS = {
    "Ownership": EMOJI_OWNERSHIP,
    "Leadership": EMOJI_LEADERSHIP,
    "Management": EMOJI_MANAGEMENT,
    "Staff": EMOJI_STAFF,
}

# ============================================================
# BOT SETUP
# ============================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
)

refresh_locks = {}
startup_refresh_done = set()


# ============================================================
# SAVE / LOAD PANEL MESSAGE ID
# ============================================================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load saved roster state: {error}")
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=4)
    except OSError as error:
        print(f"Could not save roster state: {error}")


# ============================================================
# STAFF HELPERS
# ============================================================

def get_highest_staff_role(member):
    if member.bot:
        return None

    member_role_ids = {role.id for role in member.roles}

    for group in GROUPS:
        if group["role_id"] in member_role_ids:
            return group

    return None


def get_department_mentions(member):
    highest = get_highest_staff_role(member)

    if not highest or highest["role_id"] != MANAGEMENT_ROLE_ID:
        return ""

    member_role_ids = {role.id for role in member.roles}
    mentions = []

    for role_id in DEPARTMENT_ROLE_IDS:
        if role_id in member_role_ids:
            role = member.guild.get_role(role_id)
            if role:
                mentions.append(role.mention)

    return (" " + " ".join(mentions)) if mentions else ""


def get_unique_role_members(guild, role_id):
    members = []

    for member in guild.members:
        if member.bot:
            continue

        highest = get_highest_staff_role(member)

        if highest and highest["role_id"] == role_id:
            members.append(member)

    return sorted(members, key=lambda member: member.display_name.casefold())


def format_member_line(member, group):
    line = member.mention

    if group["role_id"] == MANAGEMENT_ROLE_ID:
        line += get_department_mentions(member)

    return line


# ============================================================
# BUILD ROSTER EMBED
# ============================================================

async def create_roster_embed(guild):
    try:
        await guild.chunk(cache=True)
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Member cache warning: {error}")

    lines = []

    for section in SECTION_ORDER:
        section_groups = [
            group for group in GROUPS
            if group["section"] == section
        ]

        if not section_groups:
            continue

        lines.append(f"{SECTION_EMOJIS[section]} **{section}**")
        lines.append("")

        for group in section_groups:
            role = guild.get_role(group["role_id"])

            if role is None:
                print(
                    f"WARNING: Role '{group['name']}' "
                    f"({group['role_id']}) was not found."
                )
                lines.append(f"**{group['name']}** — Role not found")
                lines.append("N/A")
                lines.append("")
                continue

            members = get_unique_role_members(guild, group["role_id"])

            if group["target"] is None:
                count = "N/A"
            else:
                count = f"{len(members)}/{group['target']}"

            # Role ping and count appear on the same line.
            lines.append(f"{role.mention} — {count}")

            if members:
                for member in members:
                    lines.append(format_member_line(member, group))
            else:
                lines.append("N/A")

            lines.append("")

        lines.append("---")
        lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    if lines and lines[-1] == "---":
        lines.pop()

    description = "\n".join(lines).strip()

    # Discord embed descriptions are limited to 4096 characters.
    if len(description) > 4096:
        description = description[:4000].rsplit("\n", 1)[0]
        description += "\n\nRoster shortened: Discord embed limit reached."

    embed = discord.Embed(
        title=f"{EMOJI_TEAM} SNM STAFF ROSTER",
        description=description or "No staff members to display.",
        colour=discord.Colour(EMBED_COLOUR),
    )

    # No footer.
    return embed


# ============================================================
# FIND AN EXISTING ROSTER PANEL
# ============================================================

def is_roster_panel(message):
    return (
        bot.user is not None
        and message.author.id == bot.user.id
        and len(message.embeds) > 0
        and message.embeds[0].title is not None
        and "SNM STAFF ROSTER" in message.embeds[0].title.upper()
    )


async def find_existing_panel(channel):
    try:
        async for message in channel.history(limit=500):
            if is_roster_panel(message):
                return message
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Could not search channel history: {error}")
        print("Check View Channel and Read Message History permissions.")

    return None


# ============================================================
# SEND OR UPDATE THE ROSTER AUTOMATICALLY
# ============================================================

async def refresh_roster(guild):
    lock = refresh_locks.setdefault(guild.id, asyncio.Lock())

    async with lock:
        print(f"Starting roster refresh for {guild.name} ({guild.id})")

        # Find the configured channel.
        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
            except discord.NotFound:
                print(f"ERROR: Channel {ROSTER_CHANNEL_ID} does not exist.")
                return
            except discord.Forbidden:
                print("ERROR: Bot cannot access the configured roster channel.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching roster channel: {error}")
                return

        if not isinstance(channel, discord.TextChannel):
            print("ERROR: Configured roster channel is not a text channel.")
            return

        if channel.guild.id != guild.id:
            print("ERROR: Roster channel belongs to a different server.")
            return

        # Verify that the bot can send and embed messages.
        permissions = channel.permissions_for(guild.me)

        if not permissions.view_channel:
            print("ERROR: Bot needs View Channel permission.")
            return

        if not permissions.send_messages:
            print("ERROR: Bot needs Send Messages permission.")
            return

        if not permissions.embed_links:
            print("ERROR: Bot needs Embed Links permission.")
            return

        # Build the embed.
        try:
            embed = await create_roster_embed(guild)
        except Exception as error:
            print(f"ERROR building roster embed: {type(error).__name__}: {error}")
            return

        state = load_state()
        guild_key = str(guild.id)
        saved_message_id = state.get(guild_key)
        roster_message = None

        # First try the saved message ID.
        if saved_message_id:
            try:
                candidate = await channel.fetch_message(int(saved_message_id))
                if is_roster_panel(candidate):
                    roster_message = candidate
            except discord.NotFound:
                print("Saved roster message was deleted. Searching for a replacement.")
            except (ValueError, TypeError):
                print("Saved roster message ID is invalid.")
            except discord.Forbidden:
                print("ERROR: Bot cannot read the saved roster message.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching saved roster message: {error}")
                return

        # Search channel history if the saved message is missing.
        if roster_message is None:
            roster_message = await find_existing_panel(channel)

        # Edit the existing message or send a new one.
        try:
            if roster_message is not None:
                await roster_message.edit(embed=embed)
                print(f"SUCCESS: Existing roster panel updated: {roster_message.id}")
            else:
                roster_message = await channel.send(embed=embed)
                print(f"SUCCESS: NEW roster embed SENT to channel {channel.id}")
                print(f"Roster message ID: {roster_message.id}")

            state[guild_key] = roster_message.id
            save_state(state)

        except discord.Forbidden:
            print("ERROR: Discord denied permission to send or edit the roster embed.")
        except discord.HTTPException as error:
            print(f"ERROR sending/editing roster embed: {error}")


# ============================================================
# AUTOMATIC STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s).")

    # Prevent duplicate startup refreshes if Discord reconnects.
    for guild in bot.guilds:
        if guild.id in startup_refresh_done:
            continue

        startup_refresh_done.add(guild.id)

        try:
            print(f"Automatically posting roster for {guild.name}...")
            await refresh_roster(guild)
        except Exception as error:
            print(
                f"STARTUP ROSTER ERROR: {type(error).__name__}: {error}"
            )
            startup_refresh_done.discard(guild.id)

    print("Automatic roster startup check finished.")


# ============================================================
# AUTOMATIC UPDATES WHEN STAFF CHANGES
# ============================================================

@bot.event
async def on_member_update(before, after):
    if (
        before.roles != after.roles
        or before.display_name != after.display_name
    ):
        await refresh_roster(after.guild)


@bot.event
async def on_member_join(member):
    await refresh_roster(member.guild)


@bot.event
async def on_member_remove(member):
    await refresh_roster(member.guild)


@bot.event
async def on_guild_role_update(before, after):
    await refresh_roster(after.guild)


@bot.event
async def on_guild_role_delete(role):
    await refresh_roster(role.guild)


# ============================================================
# OPTIONAL ADMIN COMMANDS
# The roster does not depend on these commands.
# ============================================================

@bot.command(name="refresh_roster")
@commands.has_permissions(administrator=True)
async def refresh_roster_command(ctx):
    await refresh_roster(ctx.guild)
    await ctx.send("Roster refresh attempted.", delete_after=5)


@bot.command(name="setup_roster")
@commands.has_permissions(administrator=True)
async def setup_roster_command(ctx):
    await refresh_roster(ctx.guild)
    await ctx.send("Roster setup attempted.", delete_after=5)


@refresh_roster_command.error
async def refresh_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission to use this command.")
    else:
        print(f"Refresh command error: {type(error).__name__}: {error}")
        await ctx.send("Roster refresh failed. Check the Railway logs.")


@setup_roster_command.error
async def setup_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission to use this command.")
    else:
        print(f"Setup command error: {type(error).__name__}: {error}")
        await ctx.send("Roster setup failed. Check the Railway logs.")


# ============================================================
# START BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to Railway Variables."
    )

bot.run(BOT_TOKEN)
