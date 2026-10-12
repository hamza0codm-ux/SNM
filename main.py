
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
STATE_FILE = "roster_state.json"
ROSTER_TITLE = "SNM STAFF ROSTER"
ACCENT_COLOUR = 0x5865F2

EMOJI_TEAM = "<:Team:1354594711540863148>"
EMOJI_OWNERSHIP = "<:SNM_Staff:1476982311588204697>"
EMOJI_LEADERSHIP = "<:SNM_Directors:1476982272795082874>"
EMOJI_MANAGEMENT = "<:SNM_Management:1476982218558537950>"
EMOJI_STAFF = "<:SNM_Trial_Staff:1476982367464849439>"

# ============================================================
# STAFF HIERARCHY
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

SECTIONS = [
    ("Ownership", EMOJI_OWNERSHIP),
    ("Leadership", EMOJI_LEADERSHIP),
    ("Management", EMOJI_MANAGEMENT),
    ("Staff", EMOJI_STAFF),
]

# ============================================================
# BOT
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
startup_done = set()
refresh_tasks = {}


# ============================================================
# MESSAGE STATE
# ============================================================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"State-file warning: {error}")
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

    role_ids = {role.id for role in member.roles}

    for group in GROUPS:
        if group["role_id"] in role_ids:
            return group

    return None


def get_staff_members(guild, role_id):
    result = []

    for member in guild.members:
        if member.bot:
            continue

        highest = get_highest_staff_role(member)

        if highest and highest["role_id"] == role_id:
            result.append(member)

    return sorted(
        result,
        key=lambda member: member.display_name.casefold(),
    )


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


def format_member(member, group):
    result = member.mention

    if group["role_id"] == MANAGEMENT_ROLE_ID:
        result += get_department_mentions(member)

    return result


# ============================================================
# BUILD COMPONENTS V2 LAYOUT
# ============================================================

async def create_roster_view(guild):
    # Do not block roster creation indefinitely waiting for a cache chunk.
    try:
        await asyncio.wait_for(guild.chunk(cache=True), timeout=10)
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

    for section_index, (section_name, section_emoji) in enumerate(SECTIONS):
        lines = [
            f"## {section_emoji} {section_name}",
            "",
        ]

        groups = [
            group for group in GROUPS
            if group["section"] == section_name
        ]

        for group in groups:
            role = guild.get_role(group["role_id"])

            if role is None:
                print(
                    f"Missing role: {group['name']} "
                    f"({group['role_id']})"
                )
                lines.append(f"**{group['name']}** — N/A")
                lines.append("N/A")
                lines.append("")
                continue

            members = get_staff_members(guild, group["role_id"])

            if group["target"] is None:
                count = "N/A"
            else:
                count = f"{len(members)}/{group['target']}"

            lines.append(f"{role.mention} — {count}")

            if members:
                for member in members:
                    lines.append(format_member(member, group))
            else:
                lines.append("N/A")

            lines.append("")

        text = "\n".join(lines).strip()

        # Keep each TextDisplay comfortably below Discord's text limit.
        chunks = []
        current_lines = []
        current_length = 0

        for line in text.splitlines():
            added_length = len(line) + (1 if current_lines else 0)

            if current_lines and current_length + added_length > 3800:
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

        # Native Components V2 separator.
        # Omit the spacing argument for compatibility.
        if section_index < len(SECTIONS) - 1:
            container.add_item(
                discord.ui.Separator(visible=True)
            )

    view.add_item(container)
    return view


# ============================================================
# FIND AN EXISTING ROSTER
# ============================================================

def has_roster_title(data):
    if isinstance(data, dict):
        content = data.get("content")

        if isinstance(content, str) and ROSTER_TITLE in content.upper():
            return True

        return any(has_roster_title(value) for value in data.values())

    if isinstance(data, list):
        return any(has_roster_title(item) for item in data)

    return False


def is_roster_message(message):
    if bot.user is None or message.author.id != bot.user.id:
        return False

    for embed in message.embeds:
        if embed.title and ROSTER_TITLE in embed.title.upper():
            return True

    for component in message.components:
        try:
            if has_roster_title(component.to_dict()):
                return True
        except (AttributeError, TypeError, ValueError):
            pass

    return False


async def find_roster_message(channel):
    try:
        async for message in channel.history(limit=500):
            if is_roster_message(message):
                return message
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Could not search channel history: {error}")

    return None


# ============================================================
# SEND OR UPDATE THE ROSTER
# ============================================================

async def refresh_roster(guild):
    lock = refresh_locks.setdefault(guild.id, asyncio.Lock())

    async with lock:
        print(f"Starting roster refresh for {guild.name} ({guild.id})")

        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
            except discord.NotFound:
                print("ERROR: Roster channel not found.")
                return
            except discord.Forbidden:
                print("ERROR: Bot cannot access roster channel.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching roster channel: {error}")
                return

        if not isinstance(channel, discord.TextChannel):
            print("ERROR: Roster channel is not a text channel.")
            return

        if channel.guild.id != guild.id:
            print("ERROR: Roster channel belongs to another server.")
            return

        me = guild.me

        if me is None:
            print("ERROR: Could not resolve the bot's server member.")
            return

        permissions = channel.permissions_for(me)

        if not permissions.view_channel:
            print("ERROR: Missing View Channel permission.")
            return

        if not permissions.send_messages:
            print("ERROR: Missing Send Messages permission.")
            return

        if not permissions.read_message_history:
            print("ERROR: Missing Read Message History permission.")
            return

        state = load_state()
        guild_key = str(guild.id)
        saved_id = state.get(guild_key)

        roster_message = None

        # Look for the saved panel.
        if saved_id:
            try:
                candidate = await channel.fetch_message(int(saved_id))

                # If this is the saved message, it is our panel.
                if candidate.author.id == bot.user.id:
                    roster_message = candidate

            except discord.NotFound:
                print("Saved roster was deleted; creating a replacement.")
            except (ValueError, TypeError):
                print("Saved roster message ID is invalid.")
            except discord.Forbidden:
                print("ERROR: Cannot access the saved roster message.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching saved roster: {error}")
                return

        if roster_message is None:
            roster_message = await find_roster_message(channel)

        try:
            view = await create_roster_view(guild)
        except Exception as error:
            print(
                f"ERROR building V2 layout: "
                f"{type(error).__name__}: {error}"
            )
            return

        try:
            if roster_message is not None and roster_message.embeds:
                # Delete the legacy embed panel first. Components V2
                # cannot be combined with a traditional embed.
                print("Removing legacy embed panel for V2 conversion.")
                await roster_message.delete()
                roster_message = None

            if roster_message is None:
                print("No V2 panel found. Sending a new roster...")
                roster_message = await channel.send(view=view)
                print(f"SUCCESS: New V2 roster sent: {roster_message.id}")
            else:
                # Never pass embed= and embeds= together.
                await roster_message.edit(view=view)
                print(f"SUCCESS: V2 roster updated: {roster_message.id}")

            state[guild_key] = roster_message.id
            save_state(state)

        except Exception as error:
            print(
                f"ERROR sending/editing roster: "
                f"{type(error).__name__}: {error}"
            )


# ============================================================
# AUTOMATIC REFRESH SCHEDULING
# ============================================================

def schedule_refresh(guild):
    existing_task = refresh_tasks.get(guild.id)

    if existing_task and not existing_task.done():
        return

    async def runner():
        try:
            # Brief delay groups rapid role changes into one refresh.
            await asyncio.sleep(1)
            await refresh_roster(guild)
        except Exception as error:
            print(
                f"Scheduled refresh error: "
                f"{type(error).__name__}: {error}"
            )
        finally:
            refresh_tasks.pop(guild.id, None)

    refresh_tasks[guild.id] = asyncio.create_task(runner())


# ============================================================
# STARTUP
# ============================================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s).")

    for guild in bot.guilds:
        if guild.id in startup_done:
            continue

        startup_done.add(guild.id)
        print(f"Automatically checking roster for {guild.name}...")
        schedule_refresh(guild)


# ============================================================
# RECREATE PANEL IF DELETED
# ============================================================

@bot.event
async def on_message_delete(message):
    if message.channel.id != ROSTER_CHANNEL_ID:
        return

    if message.guild is None:
        return

    state = load_state()
    saved_id = state.get(str(message.guild.id))

    if saved_id and str(saved_id) == str(message.id):
        print("Roster panel deleted. Recreating it...")
        schedule_refresh(message.guild)


# ============================================================
# AUTO-UPDATE ON STAFF CHANGES
# ============================================================

@bot.event
async def on_member_update(before, after):
    if (
        before.roles != after.roles
        or before.display_name != after.display_name
    ):
        print(f"Member changed: {after} — refreshing roster.")
        schedule_refresh(after.guild)


@bot.event
async def on_member_join(member):
    print(f"Member joined: {member} — refreshing roster.")
    schedule_refresh(member.guild)


@bot.event
async def on_member_remove(member):
    print(f"Member left: {member} — refreshing roster.")
    schedule_refresh(member.guild)


@bot.event
async def on_guild_role_update(before, after):
    print(f"Role updated: {after.name} — refreshing roster.")
    schedule_refresh(after.guild)


@bot.event
async def on_guild_role_delete(role):
    print(f"Role deleted: {role.name} — refreshing roster.")
    schedule_refresh(role.guild)


# ============================================================
# OPTIONAL ADMIN COMMANDS
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
        await ctx.send("You need Administrator permission.")
    else:
        print(f"Refresh command error: {type(error).__name__}: {error}")


@setup_roster_command.error
async def setup_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Administrator permission.")
    else:
        print(f"Setup command error: {type(error).__name__}: {error}")


# ============================================================
# RUN
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add it in Railway Variables."
    )

bot.run(BOT_TOKEN)
