
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

# CHANGE EMBED COLOUR HERE.
# Examples: 0x5865F2 (Discord blurple), 0x3498DB (blue),
# 0x2ECC71 (green), 0xE74C3C (red), 0xF1C40F (yellow)
EMBED_COLOUR = 0x5865F2

# Custom server emojis
EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

# Only this role displays department roles next to members.
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

# Role sections in display order.
# The member counts are calculated automatically.
GROUPS = [
    {
        "title": "Ownership",
        "emoji": EMOJI_OWNERSHIP,
        "roles": [
            ("Founder", 1558896822410547210),
            ("Owner", 1558896894678278164),
            ("Co Owner", 1558896918443327589),
        ],
    },
    {
        "title": "Leadership",
        "emoji": EMOJI_LEADERSHIP,
        "roles": [
            ("Operations", 1558896966459592704),
            ("Directors", 1558897001406406741),
        ],
    },
    {
        "title": "Management",
        "emoji": EMOJI_MANAGEMENT,
        "roles": [
            ("General Management", 1558897060441235558),
            ("Management", 1558897026568028273),
        ],
    },
    {
        "title": "Staff",
        "emoji": EMOJI_STAFF,
        "roles": [
            ("Admin", 1558897520606974112),
            ("Staff", 1558897546242429100),
            ("Trial Staff", 1558897577976528957),
        ],
    },
]

MAX_DESCRIPTION_LENGTH = 4096

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
# SAVE AND LOAD PANEL MESSAGE ID
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
# ROSTER GENERATION
# ==================================================

def role_mention(role_id: int) -> str:
    return f"<@&{role_id}>"


def get_role_members(role: discord.Role):
    """Return non-bot members currently holding this role."""
    return sorted(
        [
            member
            for member in role.members
            if not member.bot
        ],
        key=lambda member: member.display_name.casefold(),
    )


def build_member_line(
    member: discord.Member,
    staff_role_id: int,
) -> str:
    line = f"• {member.mention}"

    # Departments appear ONLY for the Management role
    # with ID 1558897026568028273.
    if staff_role_id == MANAGEMENT_ROLE_WITH_DEPARTMENTS:
        departments = [
            role_mention(department_id)
            for department_id in DEPARTMENT_ROLE_IDS
            if any(
                role.id == department_id
                for role in member.roles
            )
        ]

        if departments:
            line += " — " + " ".join(departments)

    return line


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

        for role_name, role_id in group["roles"]:
            role = guild.get_role(role_id)

            if role is None:
                print(
                    f"WARNING: Role '{role_name}' "
                    f"({role_id}) was not found."
                )
                lines.append(
                    f"**{role_name} — 0**"
                )
                lines.append(role_mention(role_id))
                lines.append("• *Role not found*")
                lines.append("")
                continue

            members = get_role_members(role)

            # Live count comes before the slash-free role listing.
            # Format: Founder / 1
            lines.append(
                f"**{role_name} / {len(members)}**"
            )
            lines.append(role_mention(role_id))

            if members:
                for member in members:
                    lines.append(
                        build_member_line(member, role_id)
                    )
            else:
                lines.append("• *No members*")

            lines.append("")

        # Horizontal divider between the four main sections.
        if group_index < len(GROUPS) - 1:
            lines.append("---")
            lines.append("")

    description = "\n".join(lines).strip()

    if len(description) > MAX_DESCRIPTION_LENGTH:
        suffix = (
            "\n\n*Roster shortened: Discord's embed "
            "description limit was reached.*"
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

    # Intentionally no footer.
    return embed


# ==================================================
# PANEL MESSAGE MANAGEMENT
# ==================================================

async def get_roster_channel():
    channel = bot.get_channel(ROSTER_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(
                ROSTER_CHANNEL_ID
            )
        except discord.HTTPException as error:
            print(f"Cannot fetch roster channel: {error}")
            return None

    if not isinstance(channel, discord.TextChannel):
        print("Roster channel must be a text channel.")
        return None

    return channel


async def find_or_create_message(channel):
    state = load_state()
    message_id = state.get("roster_message_id")

    if message_id:
        try:
            return await channel.fetch_message(
                int(message_id)
            )
        except discord.NotFound:
            print("Roster message was deleted; recreating it.")
        except discord.HTTPException as error:
            print(f"Cannot fetch roster message: {error}")
            return None

    try:
        message = await channel.send(
            embed=build_embed(channel.guild),
            allowed_mentions=discord.AllowedMentions.none(),
        )

        state["roster_message_id"] = message.id
        save_state(state)

        print(f"Created roster panel: {message.id}")
        return message

    except discord.HTTPException as error:
        print(f"Cannot create roster panel: {error}")
        return None


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
            print("Roster updated successfully.")

        except discord.HTTPException as error:
            print(f"Cannot update roster: {error}")


# ==================================================
# AUTOMATIC ROLE CHANGE DETECTION
# ==================================================

def relevant_role_ids():
    staff_ids = {
        role_id
        for group in GROUPS
        for _, role_id in group["roles"]
    }

    return staff_ids | set(DEPARTMENT_ROLE_IDS)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Roster channel: {ROSTER_CHANNEL_ID}")
    await refresh_roster()


@bot.event
async def on_member_update(before, after):
    old_roles = {role.id for role in before.roles}
    new_roles = {role.id for role in after.roles}

    changed_roles = old_roles ^ new_roles

    if changed_roles & relevant_role_ids():
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
# START BOT
# ==================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Set it in Railway Variables."
    )

bot.run(BOT_TOKEN)
