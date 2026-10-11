
import asyncio
import json
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ==================================================
# CONFIGURATION
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ROSTER_CHANNEL_ID = 1558889366565167284
STATE_FILE = Path("roster_state.json")
PREFIX = "!"

# Change the embed colour here.
# Examples:
# Blue:   0x5865F2
# Green:  0x2ECC71
# Red:    0xE74C3C
# Yellow: 0xF1C40F
# Black:  0x202225
EMBED_COLOUR = 0x5865F2

# Custom server emojis
EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

# Only this role displays department mentions.
MANAGEMENT_ROLE_WITH_DEPARTMENTS = 1558897026568028273

# Department role IDs
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

# Staff hierarchy, highest to lowest.
# Format: (display name, role ID, target count)
#
# A target of None means no target has been provided yet.
# Each member is counted ONLY in their highest-ranking
# configured staff role.

GROUPS = [
    {
        "title": "Ownership",
        "emoji": EMOJI_OWNERSHIP,
        "roles": [
            ("Founder", 1558896822410547210, 1),
            ("Owner", 1558896894678278164, 2),
            ("Co Owner", 1558896918443327589, None),
        ],
    },
    {
        "title": "Leadership",
        "emoji": EMOJI_LEADERSHIP,
        "roles": [
            ("Operations", 1558896966459592704, 4),
            ("Directors", 1558897001406406741, 8),
        ],
    },
    {
        "title": "Management",
        "emoji": EMOJI_MANAGEMENT,
        "roles": [
            ("General Management", 1558897060441235558, 4),
            ("Management", 1558897026568028273, 13),
        ],
    },
    {
        "title": "Staff",
        "emoji": EMOJI_STAFF,
        "roles": [
            ("Admin", 1558897520606974112, 5),
            ("Staff", 1558897546242429100, 10),
            ("Trial Staff", 1558897577976528957, 10),
        ],
    },
]

MAX_DESCRIPTION_LENGTH = 4096

# ==================================================
# BOT SETUP
# ==================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
)

refresh_lock = asyncio.Lock()


# ==================================================
# SAVE AND LOAD THE EXISTING PANEL MESSAGE
# ==================================================

def load_state():
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


# ==================================================
# ROLE HELPERS
# ==================================================

def role_mention(role_id: int) -> str:
    return f"<@&{role_id}>"


def all_staff_roles():
    """Return all staff roles in highest-to-lowest order."""
    result = []

    for group in GROUPS:
        for role_name, role_id, target in group["roles"]:
            result.append((role_name, role_id, target))

    return result


def highest_staff_role(member: discord.Member):
    """
    Return the member's highest configured staff role.

    The first matching role in GROUPS wins.
    Members are therefore counted only once.
    """
    member_role_ids = {
        role.id for role in member.roles
    }

    for role_name, role_id, target in all_staff_roles():
        if role_id in member_role_ids:
            return role_id

    return None


def get_unique_role_members(
    guild: discord.Guild,
    role_id: int,
):
    """
    Get members whose highest configured staff role
    is this role. This prevents duplicate counts.
    """
    role = guild.get_role(role_id)

    if role is None:
        print(f"WARNING: Role {role_id} was not found.")
        return []

    members = []

    for member in role.members:
        if member.bot:
            continue

        if highest_staff_role(member) == role_id:
            members.append(member)

    return sorted(
        members,
        key=lambda member: member.display_name.casefold(),
    )


# ==================================================
# MEMBER LISTING
# ==================================================

def build_member_line(
    member: discord.Member,
    staff_role_id: int,
) -> str:
    line = f"• {member.mention}"

    # Departments are displayed ONLY for members whose
    # highest staff role is 1558897026568028273.
    if staff_role_id == MANAGEMENT_ROLE_WITH_DEPARTMENTS:
        member_role_ids = {
            role.id for role in member.roles
        }

        department_mentions = [
            role_mention(department_id)
            for department_id in DEPARTMENT_ROLE_IDS
            if department_id in member_role_ids
        ]

        if department_mentions:
            line += " — " + " ".join(department_mentions)

    return line


# ==================================================
# EMBED GENERATION
# ==================================================

def build_description(guild: discord.Guild) -> str:
    lines = [
        f"{EMOJI_TEAM} **SNM Staff Roster**",
        "",
    ]

    for group_index, group in enumerate(GROUPS):

        # Section heading
        lines.append(
            f"{group['emoji']} **{group['title']}:**"
        )
        lines.append("")

        for role_name, role_id, target in group["roles"]:

            role = guild.get_role(role_id)

            # Count only people assigned to this highest role.
            members = get_unique_role_members(
                guild,
                role_id,
            )

            current_count = len(members)

            if target is None:
                count_text = f"{current_count}/—"
            else:
                count_text = f"{current_count}/{target}"

            # Example: Founder (1/1)
            lines.append(
                f"**{role_name} ({count_text})**"
            )

            # Actual Discord role mention
            lines.append(role_mention(role_id))

            if role is None:
                lines.append("• *Role not found*")

            elif members:
                for member in members:
                    lines.append(
                        build_member_line(
                            member,
                            role_id,
                        )
                    )

            else:
                lines.append("• *No members*")

            lines.append("")

        # Section divider between Ownership, Leadership,
        # Management, and Staff.
        if group_index < len(GROUPS) - 1:
            lines.append("---")
            lines.append("")

    description = "\n".join(lines).strip()

    # Discord embed description limit: 4096 characters.
    if len(description) > MAX_DESCRIPTION_LENGTH:
        suffix = (
            "\n\n*Roster shortened because the Discord "
            "embed description limit was reached.*"
        )

        description = (
            description[:MAX_DESCRIPTION_LENGTH - len(suffix)]
            + suffix
        )

    return description


def build_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        description=build_description(guild),
        colour=discord.Colour(EMBED_COLOUR),
    )

    # No footer, as requested.
    return embed


# ==================================================
# FIND OR CREATE THE ROSTER MESSAGE
# ==================================================

async def get_roster_channel():
    channel = bot.get_channel(ROSTER_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(
                ROSTER_CHANNEL_ID
            )
        except discord.HTTPException as error:
            print(f"Could not fetch roster channel: {error}")
            return None

    if not isinstance(channel, discord.TextChannel):
        print("The configured roster channel is not a text channel.")
        return None

    return channel


async def find_or_create_message(channel):
    state = load_state()
    message_id = state.get("roster_message_id")

    # Reuse the existing panel message if possible.
    if message_id:
        try:
            return await channel.fetch_message(
                int(message_id)
            )

        except discord.NotFound:
            print("Saved roster message was deleted; recreating it.")

        except discord.HTTPException as error:
            print(f"Could not fetch saved roster message: {error}")
            return None

    # Create the panel if there is no saved message.
    try:
        message = await channel.send(
            embed=build_embed(channel.guild),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        state["roster_message_id"] = message.id
        save_state(state)

        print(f"Created roster message: {message.id}")
        return message

    except discord.HTTPException as error:
        print(f"Could not create roster message: {error}")
        return None


# ==================================================
# REFRESH THE ROSTER
# ==================================================

async def refresh_roster():
    async with refresh_lock:

        channel = await get_roster_channel()

        if channel is None:
            return

        message = await find_or_create_message(channel)

        if message is None:
            return

        try:
            await message.edit(
                embed=build_embed(channel.guild),
                allowed_mentions=discord.AllowedMentions.none(),
            )

            print("SNM staff roster updated successfully.")

        except discord.HTTPException as error:
            print(f"Could not update roster: {error}")


# ==================================================
# AUTOMATIC ROLE CHANGE DETECTION
# ==================================================

def relevant_role_ids():
    staff_ids = {
        role_id
        for _, role_id, _ in all_staff_roles()
    }

    return staff_ids | set(DEPARTMENT_ROLE_IDS)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Roster channel: {ROSTER_CHANNEL_ID}")

    await refresh_roster()


@bot.event
async def on_member_update(before, after):
    old_role_ids = {
        role.id for role in before.roles
    }

    new_role_ids = {
        role.id for role in after.roles
    }

    changed_role_ids = old_role_ids ^ new_role_ids

    # Refresh for staff changes and department changes.
    if changed_role_ids & relevant_role_ids():
        await refresh_roster()


@bot.event
async def on_member_join(member):
    if any(
        role.id in relevant_role_ids()
        for role in member.roles
    ):
        await refresh_roster()


@bot.event
async def on_member_remove(member):
    if any(
        role.id in relevant_role_ids()
        for role in member.roles
    ):
        await refresh_roster()


# ==================================================
# MANUAL COMMANDS
# ==================================================

@bot.command(name="refresh_roster")
@commands.has_permissions(manage_guild=True)
async def refresh_roster_command(ctx):
    await refresh_roster()

    await ctx.reply(
        "Roster refresh requested.",
        mention_author=False,
    )


@bot.command(name="setup_roster")
@commands.has_permissions(manage_guild=True)
async def setup_roster_command(ctx):
    await refresh_roster()

    await ctx.reply(
        f"Roster checked in <#{ROSTER_CHANNEL_ID}>.",
        mention_author=False,
    )


@refresh_roster_command.error
@setup_roster_command.error
async def roster_command_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "You need the **Manage Server** permission.",
            mention_author=False,
        )
    else:
        print(f"Command error: {error}")

        await ctx.reply(
            "Something went wrong. Check the bot console.",
            mention_author=False,
        )


# ==================================================
# START THE BOT
# ==================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Set it in Railway Variables."
    )

bot.run(BOT_TOKEN)

