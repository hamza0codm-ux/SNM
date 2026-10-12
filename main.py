import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ROSTER_CHANNEL_ID = 1558889366565167284

# Change this colour to customise the roster embed.
# Example: blue = 0x5865F2, green = 0x2ECC71, red = 0xE74C3C
EMBED_COLOUR = 0x5865F2

EMOJI_TEAM = "<:Team:1354594711540863148>"

EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

STATE_FILE = "roster_state.json"
PREFIX = "!"

# ============================================================
# STAFF HIERARCHY
# Listed from highest rank to lowest rank.
# Members appear ONLY under their highest configured rank.
# ============================================================

GROUPS = [
    {
        "name": "Founder",
        "role_id": 1558896822410547210,
        "target": 1,
        "section": "Ownership",
    },
    {
        "name": "Owner",
        "role_id": 1558896894678278164,
        "target": 2,
        "section": "Ownership",
    },
    {
        "name": "Co Owner",
        "role_id": 1558896918443327589,
        "target": None,
        "section": "Ownership",
    },
    {
        "name": "Operations",
        "role_id": 1558896966459592704,
        "target": 4,
        "section": "Leadership",
    },
    {
        "name": "Directors",
        "role_id": 1558897001406406741,
        "target": 8,
        "section": "Leadership",
    },
    {
        "name": "General Management",
        "role_id": 1558897060441235558,
        "target": 4,
        "section": "Management",
    },
    {
        "name": "Management",
        "role_id": 1558897026568028273,
        "target": 13,
        "section": "Management",
    },
    {
        "name": "Admin",
        "role_id": 1558897520606974112,
        "target": 5,
        "section": "Management",
    },
    {
        "name": "Staff",
        "role_id": 1558897546242429100,
        "target": 10,
        "section": "Staff",
    },
    {
        "name": "Trial Staff",
        "role_id": 1558897577976528957,
        "target": 10,
        "section": "Staff",
    },
]

# ============================================================
# DEPARTMENT ROLE IDS
# Only members whose highest configured staff rank is
# Management will have these department roles displayed.
# ============================================================

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

MANAGEMENT_ROLE_ID = 1558897026568028273

SECTION_EMOJIS = {
    "Ownership": EMOJI_OWNERSHIP,
    "Leadership": EMOJI_LEADERSHIP,
    "Management": EMOJI_MANAGEMENT,
    "Staff": EMOJI_STAFF,
}

SECTION_ORDER = [
    "Ownership",
    "Leadership",
    "Management",
    "Staff",
]

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

# Prevent simultaneous refreshes from creating duplicate panels.
refresh_locks = {}


# ============================================================
# SAVE / LOAD PANEL STATE
# ============================================================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

            if isinstance(data, dict):
                return data

    except FileNotFoundError:
        pass

    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load roster state: {error}")

    return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(state, file, indent=4)

    except OSError as error:
        print(f"Could not save roster state: {error}")


# ============================================================
# ROLE HELPERS
# ============================================================

def get_highest_staff_role(member):
    """
    Return the highest configured staff role a member has.
    GROUPS is ordered from highest to lowest.
    """

    if member.bot:
        return None

    member_role_ids = {role.id for role in member.roles}

    for group in GROUPS:
        if group["role_id"] in member_role_ids:
            return group

    return None


def get_department_mentions(member):
    """
    Show department role mentions only if Management is
    the member's highest configured staff rank.
    """

    highest_role = get_highest_staff_role(member)

    if not highest_role:
        return ""

    if highest_role["role_id"] != MANAGEMENT_ROLE_ID:
        return ""

    member_role_ids = {role.id for role in member.roles}
    mentions = []

    for role_id in DEPARTMENT_ROLE_IDS:
        if role_id in member_role_ids:
            role = member.guild.get_role(role_id)

            if role:
                mentions.append(role.mention)

    if not mentions:
        return ""

    return " " + " ".join(mentions)


def get_unique_role_members(guild, role_id):
    """
    Return non-bot members whose highest configured staff
    role is exactly the requested role.
    """

    matching_members = []

    for member in guild.members:
        if member.bot:
            continue

        highest_role = get_highest_staff_role(member)

        if highest_role and highest_role["role_id"] == role_id:
            matching_members.append(member)

    matching_members.sort(
        key=lambda member: member.display_name.casefold()
    )

    return matching_members


def get_target_text(group, member_count):
    """
    Format the current count against the configured target.
    Co Owner has no target and displays N/A.
    """

    target = group["target"]

    if target is None:
        return "N/A"

    return f"{member_count}/{target}"


def format_member_line(member, group):
    """
    Format one roster member.
    Department mentions are restricted to Management.
    """

    line = member.mention

    if group["role_id"] == MANAGEMENT_ROLE_ID:
        line += get_department_mentions(member)

    return line


# ============================================================
# BUILD ROSTER DESCRIPTION
# ============================================================

async def build_description(guild):
    lines = []

    # Keep the member cache as up to date as Discord permits.
    try:
        await guild.chunk(cache=True)
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Could not fully refresh member cache: {error}")

    for section in SECTION_ORDER:
        section_groups = [
            group
            for group in GROUPS
            if group["section"] == section
        ]

        if not section_groups:
            continue

        section_emoji = SECTION_EMOJIS.get(section, "")

        lines.append(f"{section_emoji} **{section}**")
        lines.append("")

        for group in section_groups:
            role = guild.get_role(group["role_id"])

            # If a configured role was deleted, show a warning
            # rather than silently using a different role.
            if role is None:
                lines.append(
                    f"**{group['name']}** — Role not found"
                )
                lines.append("N/A")
                lines.append("")
                continue

            members = get_unique_role_members(
                guild,
                group["role_id"],
            )

            count_text = get_target_text(group, len(members))

            # The role mention and count are on the same line.
            lines.append(f"{role.mention} — {count_text}")

            if members:
                for member in members:
                    lines.append(format_member_line(member, group))
            else:
                lines.append("N/A")

            lines.append("")

        lines.append("---")
        lines.append("")

    # Remove the final separator so the embed ends neatly.
    while lines and lines[-1] == "":
        lines.pop()

    if lines and lines[-1] == "---":
        lines.pop()

    description = "\n".join(lines).strip()

    # Discord embed descriptions have a 4096-character limit.
    if len(description) > 4096:
        description = description[:4050].rsplit("\n", 1)[0]
        description += "\n\nRoster shortened because it exceeds Discord's embed limit."

    return description or "No staff members to display."


# ============================================================
# CREATE EMBED
# ============================================================

async def create_roster_embed(guild):
    description = await build_description(guild)

    embed = discord.Embed(
        title=f"{EMOJI_TEAM} SNM STAFF ROSTER",
        description=description,
        colour=discord.Colour(EMBED_COLOUR),
    )

    # Intentionally no footer.
    return embed


# ============================================================
# FIND THE EXISTING PANEL
# ============================================================

def is_roster_panel(message):
    if bot.user is None:
        return False

    if message.author.id != bot.user.id:
        return False

    if not message.embeds:
        return False

    title = message.embeds[0].title

    return bool(
        title and "SNM STAFF ROSTER" in title.upper()
    )


async def find_existing_panel(channel):
    """
    Search recent channel history for an existing roster embed.
    This allows recovery if the saved message was deleted
    or the bot's local state file was reset.
    """

    try:
        async for message in channel.history(limit=500):
            if is_roster_panel(message):
                return message

    except (discord.Forbidden, discord.HTTPException) as error:
        print(
            "Could not search roster channel history. "
            "Check the bot's View Channel and Read Message History "
            f"permissions. Details: {error}"
        )
        return None

    return None


# ============================================================
# REFRESH / CREATE ROSTER PANEL
# ============================================================

async def refresh_roster(guild):
    """
    Update the existing roster panel if possible.
    If the old panel was deleted or cannot be found,
    create a replacement and save its message ID.
    """

    lock = refresh_locks.setdefault(
        guild.id,
        __import__("asyncio").Lock(),
    )

    async with lock:
        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(
                    ROSTER_CHANNEL_ID
                )

            except (
                discord.NotFound,
                discord.Forbidden,
                discord.HTTPException,
            ) as error:
                print(
                    f"Could not access roster channel "
                    f"{ROSTER_CHANNEL_ID}: {error}"
                )
                return

        if not isinstance(channel, discord.TextChannel):
            print("The configured roster channel is not a text channel.")
            return

        if channel.guild.id != guild.id:
            print("The configured roster channel belongs to another server.")
            return

        try:
            await guild.chunk(cache=True)
        except (discord.Forbidden, discord.HTTPException) as error:
            print(f"Could not refresh member cache: {error}")

        # Build the embed using the latest available member cache.
        embed = await create_roster_embed(guild)

        state = load_state()
        guild_key = str(guild.id)
        saved_message_id = state.get(guild_key)

        roster_message = None

        # First, try the message ID saved locally.
        if saved_message_id:
            try:
                message = await channel.fetch_message(
                    int(saved_message_id)
                )

                if is_roster_panel(message):
                    roster_message = message

            except discord.NotFound:
                print(
                    "Saved roster panel was deleted. "
                    "Searching for an existing panel."
                )

            except (ValueError, TypeError):
                print("Saved roster message ID is invalid.")

            except (
                discord.Forbidden,
                discord.HTTPException,
            ) as error:
                print(f"Could not fetch saved panel: {error}")
                return

        # If the saved panel is missing, search channel history.
        if roster_message is None:
            roster_message = await find_existing_panel(channel)

        # Create a replacement only if no existing panel was found.
        try:
            if roster_message is not None:
                await roster_message.edit(embed=embed)

                print(
                    "Existing roster panel updated: "
                    f"{roster_message.id}"
                )

            else:
                roster_message = await channel.send(embed=embed)

                print(
                    "New roster panel created: "
                    f"{roster_message.id}"
                )

            # Save the message ID for the next refresh.
            state[guild_key] = roster_message.id
            save_state(state)

        except discord.Forbidden:
            print(
                "Permission denied. The bot needs View Channel, "
                "Send Messages, Embed Links, Read Message History, "
                "and permission to edit its own roster message."
            )

        except discord.HTTPException as error:
            print(f"Discord rejected the roster update: {error}")


# ============================================================
# BOT EVENTS
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("SNM Staff Roster bot is online.")

    for guild in bot.guilds:
        await refresh_roster(guild)


@bot.event
async def on_member_update(before, after):
    # Only refresh if the member's roles or display name changed.
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
# ADMIN COMMANDS
# ============================================================

@bot.command(name="refresh_roster")
@commands.has_permissions(administrator=True)
async def refresh_roster_command(ctx):
    """
    Manually refresh the roster.
    Usage: !refresh_roster
    """

    await refresh_roster(ctx.guild)

    await ctx.send(
        "Roster refresh requested.",
        delete_after=5,
    )


@bot.command(name="setup_roster")
@commands.has_permissions(administrator=True)
async def setup_roster_command(ctx):
    """
    Find and update the existing panel, or create one if missing.
    Usage: !setup_roster
    """

    await refresh_roster(ctx.guild)

    await ctx.send(
        "Roster setup completed. Check the roster channel.",
        delete_after=5,
    )


# ============================================================
# COMMAND ERROR HANDLING
# ============================================================

@refresh_roster_command.error
async def refresh_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "You need Administrator permission to use this command.",
            delete_after=5,
        )
    else:
        print(f"Refresh command error: {error}")
        await ctx.send(
            "Something went wrong while refreshing the roster. "
            "Check the Railway logs.",
            delete_after=8,
        )


@setup_roster_command.error
async def setup_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "You need Administrator permission to use this command.",
            delete_after=5,
        )
    else:
        print(f"Setup command error: {error}")
        await ctx.send(
            "Something went wrong while setting up the roster. "
            "Check the Railway logs.",
            delete_after=8,
        )


# ============================================================
# START BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to your Railway "
        "Variables or to your local .env file."
    )

bot.run(BOT_TOKEN)
