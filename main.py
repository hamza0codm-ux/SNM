
import asyncio
import json
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ROSTER_CHANNEL_ID = 1558889366565167284
STATE_FILE = Path("roster_state.json")
PREFIX = "!"

# Custom server emojis
EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

# Staff roster sections, in your requested order
GROUPS = [
    {
        "title": "Ownership Team",
        "emoji": EMOJI_OWNERSHIP,
        "roles": [
            1558896822410547210,
            1558896894678278164,
            1558896918443327589,
        ],
    },
    {
        "title": "Leadership Team",
        "emoji": EMOJI_LEADERSHIP,
        "roles": [
            1558896966459592704,
            1558897001406406741,
        ],
    },
    {
        "title": "Management",
        "emoji": EMOJI_MANAGEMENT,
        "roles": [
            1558897060441235558,
            1558897026568028273,
        ],
    },
    {
        "title": "Staff",
        "emoji": EMOJI_STAFF,
        "roles": [
            1558897520606974112,
            1558897546242429100,
            1558897577976528957,
        ],
    },
]

# Only this staff role displays department roles beside members
MANAGEMENT_ROLE_WITH_DEPARTMENTS = 1558897026568028273

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

DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
MAX_DESCRIPTION_LENGTH = 4096

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
refresh_lock = asyncio.Lock()


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


def role_mention(role_id: int) -> str:
    return f"<@&{role_id}>"


def build_member_line(
    member: discord.Member,
    staff_role_id: int,
) -> str:
    line = f"• {member.mention}"

    # Department roles are shown only for this management role.
    if staff_role_id == MANAGEMENT_ROLE_WITH_DEPARTMENTS:
        department_mentions = [
            role_mention(role_id)
            for role_id in DEPARTMENT_ROLE_IDS
            if any(
                member_role.id == role_id
                for member_role in member.roles
            )
        ]

        if department_mentions:
            line += " — " + " ".join(department_mentions)

    return line


def build_description(guild: discord.Guild) -> str:
    lines = [
        f"{EMOJI_TEAM} **SNM Staff Roster**",
        "",
        DIVIDER,
        "",
    ]

    for group_index, group in enumerate(GROUPS):
        lines.append(
            f"{group['emoji']} **{group['title']}:**"
        )

        for role_id in group["roles"]:
            role = guild.get_role(role_id)

            # Display the actual Discord role mention.
            lines.append(role_mention(role_id))

            if role is None:
                print(f"Warning: Role {role_id} not found.")
                members = []
            else:
                members = sorted(
                    (
                        member
                        for member in role.members
                        if not member.bot
                    ),
                    key=lambda member: member.display_name.casefold(),
                )

            if members:
                for member in members:
                    lines.append(
                        build_member_line(member, role_id)
                    )
            else:
                lines.append("• *No members*")

            # Divider after every role
            lines.append(DIVIDER)

        if group_index < len(GROUPS) - 1:
            lines.append("")

    description = "\n".join(lines)

    # Discord embed descriptions have a 4096-character limit.
    if len(description) > MAX_DESCRIPTION_LENGTH:
        suffix = (
            "\n\n*Roster shortened because it exceeded "
            "Discord's 4096-character limit.*"
        )
        description = (
            description[:MAX_DESCRIPTION_LENGTH - len(suffix)]
            + suffix
        )

    return description


def build_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        description=build_description(guild),
        color=discord.Color.from_rgb(46, 125, 220),
    )
    embed.set_footer(
        text="Automatically updated when staff roles change"
    )
    return embed


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
        print("The configured channel is not a text channel.")
        return None

    return channel


async def find_or_create_message(channel):
    state = load_state()
    message_id = state.get("roster_message_id")

    # Reuse the existing panel whenever possible.
    if message_id:
        try:
            return await channel.fetch_message(
                int(message_id)
            )
        except discord.NotFound:
            print("Saved roster message was deleted.")
        except discord.HTTPException as error:
            print(f"Could not fetch saved message: {error}")
            return None

    # Create the panel if one has not been saved yet.
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
            print("Staff roster updated.")

        except discord.HTTPException as error:
            print(f"Could not update roster: {error}")


# Check whether a member has any relevant configured role.
def has_relevant_role(member: discord.Member) -> bool:
    staff_role_ids = {
        role_id
        for group in GROUPS
        for role_id in group["roles"]
    }

    relevant_ids = staff_role_ids | set(DEPARTMENT_ROLE_IDS)

    return any(
        role.id in relevant_ids
        for role in member.roles
    )


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Roster channel: {ROSTER_CHANNEL_ID}")

    await refresh_roster()


@bot.event
async def on_member_update(before, after):
    before_roles = {
        role.id for role in before.roles
    }
    after_roles = {
        role.id for role in after.roles
    }

    changed_roles = before_roles ^ after_roles

    relevant_ids = {
        role_id
        for group in GROUPS
        for role_id in group["roles"]
    } | set(DEPARTMENT_ROLE_IDS)

    if changed_roles & relevant_ids:
        await refresh_roster()


@bot.event
async def on_member_join(member):
    if has_relevant_role(member):
        await refresh_roster()


@bot.event
async def on_member_remove(member):
    if has_relevant_role(member):
        await refresh_roster()


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


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add it to your .env file."
    )

bot.run(BOT_TOKEN)
