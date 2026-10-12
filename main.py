
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
ROSTER_STATE_FILE = "roster_state.json"
ROSTER_TITLE = "SNM STAFF ROSTER"

EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

ACCENT_COLOUR = 0x5865F2

# ============================================================
# STAFF HIERARCHY — HIGHEST RANK FIRST
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
        "target": 3,
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
        "section": "Staff",
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

SECTION_ORDER = [
    "Ownership",
    "Leadership",
    "Management",
    "Staff",
]

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
    command_prefix="!",
    intents=intents,
    help_command=None,
)

refresh_locks = {}
startup_refresh_done = set()


# ============================================================
# STATE FILE
# ============================================================

def load_state():
    try:
        with open(ROSTER_STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load roster state: {error}")
        return {}


def save_state(state):
    try:
        with open(ROSTER_STATE_FILE, "w", encoding="utf-8") as file:
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

    return " " + " ".join(mentions) if mentions else ""


def get_unique_role_members(guild, role_id):
    members = []

    for member in guild.members:
        if member.bot:
            continue

        highest = get_highest_staff_role(member)

        # Count a member only under their highest configured staff rank.
        if highest and highest["role_id"] == role_id:
            members.append(member)

    return sorted(
        members,
        key=lambda member: member.display_name.casefold(),
    )


def format_member_line(member, group):
    result = member.mention

    if group["role_id"] == MANAGEMENT_ROLE_ID:
        result += get_department_mentions(member)

    return result


# ============================================================
# COMPONENTS V2 ROSTER BUILDER
# ============================================================

async def create_roster_view(guild):
    try:
        await asyncio.wait_for(
            guild.chunk(cache=True),
            timeout=10,
        )
    except asyncio.TimeoutError:
        print("Member-cache request timed out; continuing.")
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Member-cache warning: {error}")

    view = discord.ui.LayoutView(timeout=None)

    container = discord.ui.Container(
        accent_colour=discord.Colour(ACCENT_COLOUR)
    )

    container.add_item(
        discord.ui.TextDisplay(
            f"# {EMOJI_TEAM} {ROSTER_TITLE}"
        )
    )

    for index, section in enumerate(SECTION_ORDER):
        lines = [
            f"## {SECTION_EMOJIS[section]} {section}",
            "",
        ]

        section_groups = [
            group
            for group in GROUPS
            if group["section"] == section
        ]

        for group in section_groups:
            role = guild.get_role(group["role_id"])

            if role is None:
                print(
                    f"WARNING: Missing role {group['name']} "
                    f"({group['role_id']})"
                )
                lines.append(f"**{group['name']}** — N/A")
                lines.append("")
                continue

            members = get_unique_role_members(
                guild,
                group["role_id"],
            )

            if group["target"] is None:
                count = "N/A"
            else:
                count = f"{len(members)}/{group['target']}"

            lines.append(f"{role.mention} — {count}")

            if members:
                for member in members:
                    lines.append(format_member_line(member, group))
            else:
                lines.append("N/A")

            lines.append("")

        section_text = "\n".join(lines).strip()

        # Split long sections into valid TextDisplay components.
        chunks = []
        current_lines = []
        current_length = 0

        for line in section_text.split("\n"):
            extra = len(line) + (1 if current_lines else 0)

            if current_lines and current_length + extra > 3800:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0

            current_lines.append(line)
            current_length += len(line) + (
                1 if len(current_lines) > 1 else 0
            )

        if current_lines:
            chunks.append("\n".join(current_lines))

        for chunk in chunks:
            container.add_item(discord.ui.TextDisplay(chunk))

        # Native Discord Components V2 divider.
        if index < len(SECTION_ORDER) - 1:
            container.add_item(
                discord.ui.Separator(
                    visible=True,
                    spacing=discord.SeparatorSpacing.small,
                )
            )

    view.add_item(container)
    return view


# ============================================================
# FIND EXISTING ROSTER
# ============================================================

def contains_roster_title(data):
    if isinstance(data, dict):
        content = data.get("content")

        if (
            isinstance(content, str)
            and ROSTER_TITLE in content.upper()
        ):
            return True

        return any(
            contains_roster_title(value)
            for value in data.values()
        )

    if isinstance(data, list):
        return any(contains_roster_title(item) for item in data)

    return False


def is_roster_panel(message):
    if bot.user is None or message.author.id != bot.user.id:
        return False

    # Recognise the previous embed version.
    for embed in message.embeds:
        if (
            embed.title
            and ROSTER_TITLE in embed.title.upper()
        ):
            return True

    # Recognise the new Components V2 version.
    for component in message.components:
        try:
            if contains_roster_title(component.to_dict()):
                return True
        except (AttributeError, TypeError, ValueError):
            continue

    return False


async def find_existing_panel(channel):
    try:
        async for message in channel.history(limit=500):
            if is_roster_panel(message):
                return message
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Could not search roster history: {error}")

    return None


# ============================================================
# REFRESH / RECREATE ROSTER
# ============================================================

async def refresh_roster(guild):
    lock = refresh_locks.setdefault(
        guild.id,
        asyncio.Lock(),
    )

    async with lock:
        print(
            f"Starting roster refresh for "
            f"{guild.name} ({guild.id})"
        )

        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(
                    ROSTER_CHANNEL_ID
                )
            except discord.NotFound:
                print("ERROR: Roster channel was not found.")
                return
            except discord.Forbidden:
                print("ERROR: Bot cannot access roster channel.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching channel: {error}")
                return

        if not isinstance(channel, discord.TextChannel):
            print("ERROR: Roster channel is not a text channel.")
            return

        if channel.guild.id != guild.id:
            print("ERROR: Roster channel belongs to another server.")
            return

        permissions = channel.permissions_for(guild.me)

        if not permissions.view_channel:
            print("ERROR: Missing View Channel permission.")
            return

        if not permissions.send_messages:
            print("ERROR: Missing Send Messages permission.")
            return

        if not permissions.read_message_history:
            print("ERROR: Missing Read Message History permission.")
            return

        if not permissions.embed_links:
            print(
                "WARNING: Embed Links permission is missing. "
                "Components V2 may fail to send."
            )

        try:
            view = await create_roster_view(guild)
        except Exception as error:
            print(
                f"ERROR building roster: "
                f"{type(error).__name__}: {error}"
            )
            return

        state = load_state()
        guild_key = str(guild.id)
        saved_id = state.get(guild_key)
        roster_message = None

        # Try the saved message first.
        if saved_id:
            try:
                candidate = await channel.fetch_message(int(saved_id))

                if is_roster_panel(candidate):
                    roster_message = candidate

            except discord.NotFound:
                print(
                    "Saved panel was deleted. "
                    "A replacement will be created if none is found."
                )
            except (ValueError, TypeError):
                print("Saved roster message ID is invalid.")
            except discord.Forbidden:
                print("ERROR: Cannot read the saved roster message.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching saved message: {error}")
                return

        # Search for a panel if the saved ID no longer works.
        if roster_message is None:
            roster_message = await find_existing_panel(channel)

        try:
            if roster_message is not None:
                await roster_message.edit(
                    content=None,
                    embed=None,
                    embeds=[],
                    attachments=[],
                    view=view,
                )

                print(
                    f"SUCCESS: V2 roster updated "
                    f"(message ID: {roster_message.id})"
                )
            else:
                print("No existing panel found. Creating a new one.")

                roster_message = await channel.send(view=view)

                print(
                    f"SUCCESS: New V2 roster sent "
                    f"(message ID: {roster_message.id})"
                )

            state[guild_key] = roster_message.id
            save_state(state)

        except Exception as error:
            print(
                f"ERROR sending/editing roster: "
                f"{type(error).__name__}: {error}"
            )


# ============================================================
# AUTOMATIC STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s).")

    for guild in bot.guilds:
        if guild.id in startup_refresh_done:
            continue

        startup_refresh_done.add(guild.id)

        try:
            print(f"Automatically checking roster for {guild.name}...")
            await refresh_roster(guild)
        except Exception as error:
            startup_refresh_done.discard(guild.id)
            print(
                f"STARTUP ERROR: "
                f"{type(error).__name__}: {error}"
            )

    print("Startup roster check finished.")


# ============================================================
# RECREATE PANEL WHEN THE ROSTER MESSAGE IS DELETED
# ============================================================

@bot.event
async def on_message_delete(message):
    if message.channel.id != ROSTER_CHANNEL_ID:
        return

    state = load_state()
    guild_key = str(message.guild.id) if message.guild else None

    if not guild_key:
        return

    saved_id = state.get(guild_key)

    was_saved_panel = (
        saved_id is not None
        and str(saved_id) == str(message.id)
    )

    was_roster_panel = is_roster_panel(message)

    if was_saved_panel or was_roster_panel:
        print("Roster panel deleted. Recreating it...")
        await asyncio.sleep(2)

        guild = message.guild

        if guild:
            await refresh_roster(guild)


# ============================================================
# AUTOMATIC STAFF UPDATES
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
# ============================================================

@bot.command(name="refresh_roster")
@commands.has_permissions(administrator=True)
async def refresh_roster_command(ctx):
    await refresh_roster(ctx.guild)


@bot.command(name="setup_roster")
@commands.has_permissions(administrator=True)
async def setup_roster_command(ctx):
    await refresh_roster(ctx.guild)


@refresh_roster_command.error
async def refresh_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "You need Administrator permission to use this command."
        )
    else:
        print(f"Refresh command error: {error}")


@setup_roster_command.error
async def setup_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "You need Administrator permission to use this command."
        )
    else:
        print(f"Setup command error: {error}")


# ============================================================
# START BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to Railway Variables."
    )

bot.run(BOT_TOKEN)
