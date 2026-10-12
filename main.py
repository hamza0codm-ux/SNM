
import os
import json

import discord
from discord.ext import commands
from dotenv import load_dotenv


# =========================================================
# SETTINGS — CHANGE THESE HERE
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

ROSTER_CHANNEL_ID = 1558889366565167284

STATE_FILE = "roster_state.json"

PREFIX = "!"

# Embed colour: change this hex value if you want another colour.
EMBED_COLOUR = 0x5865F2


# =========================================================
# CUSTOM EMOJIS
# =========================================================

EMOJI_TEAM = "<:Team:1354594711540863148>"

EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"


# =========================================================
# STAFF ROLES
# Listed from highest rank to lowest rank.
# Members are counted ONLY under their highest role.
# =========================================================

GROUPS = [
    {
        "name": "Founder",
        "role_id": 1558896822410547210,
        "target": 1,
        "section": "ownership",
    },
    {
        "name": "Owner",
        "role_id": 1558896894678278164,
        "target": 2,
        "section": "ownership",
    },
    {
        "name": "Co Owner",
        "role_id": 1558896918443327589,
        "target": None,
        "section": "ownership",
    },
    {
        "name": "Operations",
        "role_id": 1558896966459592704,
        "target": 4,
        "section": "leadership",
    },
    {
        "name": "Directors",
        "role_id": 1558897001406406741,
        "target": 8,
        "section": "leadership",
    },
    {
        "name": "General Management",
        "role_id": 1558897060441235558,
        "target": 4,
        "section": "management",
    },
    {
        "name": "Management",
        "role_id": 1558897026568028273,
        "target": 13,
        "section": "management",
    },
    {
        "name": "Admin",
        "role_id": 1558897520606974112,
        "target": 5,
        "section": "staff",
    },
    {
        "name": "Staff",
        "role_id": 1558897546242429100,
        "target": 10,
        "section": "staff",
    },
    {
        "name": "Trial Staff",
        "role_id": 1558897577976528957,
        "target": 10,
        "section": "staff",
    },
]


# =========================================================
# MANAGEMENT DEPARTMENT ROLES
# These mentions appear beside Management members only.
# =========================================================

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


# =========================================================
# DISCORD BOT SETUP
# =========================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
)


# =========================================================
# SECTION HEADERS
# =========================================================

SECTION_HEADERS = {
    "ownership": f"{EMOJI_OWNERSHIP} **OWNERSHIP**",
    "leadership": f"{EMOJI_LEADERSHIP} **LEADERSHIP**",
    "management": f"{EMOJI_MANAGEMENT} **MANAGEMENT**",
    "staff": f"{EMOJI_STAFF} **STAFF**",
}

SECTION_ORDER = [
    "ownership",
    "leadership",
    "management",
    "staff",
]


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_highest_staff_role(member):
    """
    Returns the highest configured staff role held by a member.
    GROUPS is ordered from highest rank to lowest rank.
    """

    member_role_ids = {role.id for role in member.roles}

    for group in GROUPS:
        if group["role_id"] in member_role_ids:
            return group["role_id"]

    return None


def get_department_mentions(member, guild):
    """
    Returns department role mentions for Management members.
    Missing or deleted department roles are skipped.
    """

    member_role_ids = {role.id for role in member.roles}

    mentions = []

    for role_id in DEPARTMENT_ROLE_IDS:
        if role_id in member_role_ids:
            role = guild.get_role(role_id)

            if role:
                mentions.append(role.mention)

    if not mentions:
        return ""

    return " " + " ".join(mentions)


async def get_unique_role_members(guild, role_id):
    """
    Gets non-bot members who have this role as their
    highest configured staff role.
    """

    role = guild.get_role(role_id)

    if role is None:
        return []

    members = []

    for member in guild.members:
        if member.bot:
            continue

        highest_role_id = get_highest_staff_role(member)

        if highest_role_id == role_id:
            members.append(member)

    members.sort(key=lambda member: member.display_name.lower())

    return members


def format_member_line(member, guild, staff_role_id):
    """
    Formats a member mention.
    Department mentions are displayed only for Management.
    """

    line = member.mention

    if staff_role_id == MANAGEMENT_ROLE_WITH_DEPARTMENTS:
        line += get_department_mentions(member, guild)

    return line


def get_target_text(current_count, target):
    if target is None:
        return f"{current_count}/N/A"

    return f"{current_count}/{target}"


# =========================================================
# BUILD ROSTER DESCRIPTION
# =========================================================

async def build_description(guild):
    """
    Creates the roster in this format:

    @Founder 0/1
    N/A

    @Owner 1/2
    @Member
    """

    section_lines = {
        section: [SECTION_HEADERS[section]]
        for section in SECTION_ORDER
    }

    for group in GROUPS:
        role_id = group["role_id"]
        target = group["target"]
        section = group["section"]

        role = guild.get_role(role_id)

        # If the role was deleted or cannot be found,
        # show a clear placeholder.
        if role is None:
            role_line = f"**{group['name']}** N/A"
            section_lines[section].append(role_line)
            section_lines[section].append("N/A")
            section_lines[section].append("")
            continue

        members = await get_unique_role_members(guild, role_id)

        count_text = get_target_text(len(members), target)

        # IMPORTANT:
        # The role ping and count are on the SAME line.
        role_line = f"{role.mention} {count_text}"

        section_lines[section].append(role_line)

        if members:
            for member in members:
                member_line = format_member_line(
                    member,
                    guild,
                    role_id,
                )

                section_lines[section].append(member_line)
        else:
            section_lines[section].append("N/A")

        section_lines[section].append("")

    # Separate the four main sections.
    description_parts = []

    for index, section in enumerate(SECTION_ORDER):
        if index > 0:
            description_parts.append("---")

        description_parts.extend(section_lines[section])

    description = "\n".join(description_parts).strip()

    # Discord embed descriptions have a 4096-character limit.
    if len(description) > 4096:
        description = description[:4070] + "\n\nRoster shortened."

    return description


# =========================================================
# EMBED CREATION
# =========================================================

async def create_roster_embed(guild):
    description = await build_description(guild)

    embed = discord.Embed(
        title=f"{EMOJI_TEAM} SNM STAFF ROSTER",
        description=description,
        colour=discord.Colour(EMBED_COLOUR),
    )

    # Intentionally no footer.
    return embed


# =========================================================
# MESSAGE STATE
# =========================================================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=4)


# =========================================================
# REFRESH ROSTER
# =========================================================

async def refresh_roster(guild):
    channel = guild.get_channel(ROSTER_CHANNEL_ID)

    if channel is None:
        try:
            channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            print(
                f"Could not access roster channel "
                f"{ROSTER_CHANNEL_ID}."
            )
            return

    if not isinstance(channel, discord.TextChannel):
        print("The configured roster channel is not a text channel.")
        return

    # Populate the guild member cache before counting members.
    try:
        await guild.chunk(cache=True)
    except (discord.Forbidden, discord.HTTPException):
        print("Could not refresh the guild member cache.")

    embed = await create_roster_embed(guild)

    state = load_state()
    guild_key = str(guild.id)
    message_id = state.get(guild_key)

    # Edit the existing roster message if it still exists.
    if message_id:
        try:
            message = await channel.fetch_message(int(message_id))
            await message.edit(embed=embed)
            print("Staff roster updated.")
            return

        except discord.NotFound:
            print("Previous roster message was deleted. Creating a new one.")

        except (discord.Forbidden, discord.HTTPException) as error:
            print(f"Could not edit roster message: {error}")
            return

    # Send a new roster message.
    try:
        message = await channel.send(embed=embed)

        state[guild_key] = message.id
        save_state(state)

        print("Staff roster message created.")

    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Could not send roster message: {error}")


# =========================================================
# AUTOMATIC UPDATES
# =========================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}.")

    for guild in bot.guilds:
        await refresh_roster(guild)


@bot.event
async def on_member_update(before, after):
    before_roles = {role.id for role in before.roles}
    after_roles = {role.id for role in after.roles}

    if before_roles != after_roles:
        relevant_role_ids = {
            group["role_id"] for group in GROUPS
        }

        relevant_role_ids.update(DEPARTMENT_ROLE_IDS)

        changed_roles = before_roles.symmetric_difference(after_roles)

        if changed_roles.intersection(relevant_role_ids):
            await refresh_roster(after.guild)


@bot.event
async def on_member_join(member):
    await refresh_roster(member.guild)


@bot.event
async def on_member_remove(member):
    await refresh_roster(member.guild)


# =========================================================
# MANUAL COMMANDS
# =========================================================

@bot.command(name="refresh_roster")
@commands.has_permissions(administrator=True)
async def refresh_roster_command(ctx):
    await refresh_roster(ctx.guild)
    await ctx.reply("Staff roster refresh requested.", mention_author=False)


@bot.command(name="setup_roster")
@commands.has_permissions(administrator=True)
async def setup_roster_command(ctx):
    await refresh_roster(ctx.guild)
    await ctx.reply("Staff roster setup requested.", mention_author=False)


# =========================================================
# COMMAND ERROR HANDLING
# =========================================================

@refresh_roster_command.error
@setup_roster_command.error
async def roster_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "You need Administrator permission to use this command.",
            mention_author=False,
        )
    else:
        print(f"Command error: {error}")


# =========================================================
# START BOT
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to your Railway Variables."
    )

bot.run(BOT_TOKEN)
