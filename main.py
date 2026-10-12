
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
EMBED_COLOUR = 0x5865F2  # Used as the V2 container accent colour

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
    command_prefix=PREFIX,
    intents=intents,
    help_command=None,
)

refresh_locks = {}
startup_refresh_done = set()

# ============================================================
# SAVE / LOAD ROSTER MESSAGE ID
# ============================================================

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
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

    # Department mentions are only displayed for members whose
    # highest configured staff role is Management.
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

    return sorted(
        members,
        key=lambda member: member.display_name.casefold(),
    )


def format_member_line(member, group):
    line = member.mention

    if group["role_id"] == MANAGEMENT_ROLE_ID:
        line += get_department_mentions(member)

    return line


# ============================================================
# BUILD DISCORD COMPONENTS V2 ROSTER
# ============================================================

async def create_roster_view(guild):
    try:
        # Prevent a slow member-cache request from hanging startup.
        await asyncio.wait_for(
            guild.chunk(cache=True),
            timeout=10,
        )
    except asyncio.TimeoutError:
        print("Member-cache warning: chunking timed out; continuing.")
    except (discord.Forbidden, discord.HTTPException) as error:
        print(f"Member-cache warning: {error}")

    # Components V2 layout.
    view = discord.ui.LayoutView(timeout=None)

    container = discord.ui.Container(
        accent_colour=discord.Colour(EMBED_COLOUR)
    )

    # Main title.
    container.add_item(
        discord.ui.TextDisplay(
            f"# {EMOJI_TEAM} SNM STAFF ROSTER"
        )
    )

    for section_index, section in enumerate(SECTION_ORDER):
        section_lines = [
            f"## {SECTION_EMOJIS[section]} {section}",
            "",
        ]

        section_groups = [
            group for group in GROUPS
            if group["section"] == section
        ]

        for group in section_groups:
            role = guild.get_role(group["role_id"])

            if role is None:
                print(
                    f"WARNING: Role '{group['name']}' "
                    f"({group['role_id']}) was not found."
                )
                section_lines.append(
                    f"**{group['name']}** — Role not found"
                )
                section_lines.append("N/A")
                section_lines.append("")
                continue

            members = get_unique_role_members(
                guild,
                group["role_id"],
            )

            if group["target"] is None:
                count = "N/A"
            else:
                count = f"{len(members)}/{group['target']}"

            # Role mention and staff count stay on the same line.
            section_lines.append(f"{role.mention} — {count}")

            if members:
                for member in members:
                    section_lines.append(
                        format_member_line(member, group)
                    )
            else:
                section_lines.append("N/A")

            section_lines.append("")

        section_text = "\n".join(section_lines).strip()

        # Discord TextDisplay content has a character limit.
        # Split unusually large sections without cutting a line.
        chunks = []
        current_lines = []
        current_length = 0

        for line in section_text.split("\n"):
            extra_length = len(line) + (
                1 if current_lines else 0
            )

            if current_lines and current_length + extra_length > 3800:
                chunks.append("\n".join(current_lines))
                current_lines = []
                current_length = 0

            current_lines.append(line)
            current_length += len(line) + (
                1 if len(current_lines) > 1 else 0
            )

        if current_lines:
            chunks.append("\n".join(current_lines))

        if not chunks:
            chunks = [f"## {section}"]

        for chunk in chunks:
            container.add_item(
                discord.ui.TextDisplay(chunk)
            )

        # Native Discord V2 separator between sections.
        if section_index < len(SECTION_ORDER) - 1:
            container.add_item(
                discord.ui.Separator(
                    visible=True,
                    spacing=discord.SeparatorSpacingSize.small,
                )
            )

    view.add_item(container)
    return view


# ============================================================
# IDENTIFY THE EXISTING ROSTER MESSAGE
# ============================================================

def contains_roster_title(value):
    if isinstance(value, dict):
        content = value.get("content")

        if isinstance(content, str) and "SNM STAFF ROSTER" in content.upper():
            return True

        return any(
            contains_roster_title(item)
            for item in value.values()
        )

    if isinstance(value, list):
        return any(contains_roster_title(item) for item in value)

    return False


def is_roster_panel(message):
    if bot.user is None or message.author.id != bot.user.id:
        return False

    # Recognise the old embed so it can be converted to V2.
    for embed in message.embeds:
        if (
            embed.title
            and "SNM STAFF ROSTER" in embed.title.upper()
        ):
            return True

    # Recognise the new Components V2 roster.
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
        print(f"Could not search channel history: {error}")
        print("Check View Channel and Read Message History permissions.")

    return None


# ============================================================
# AUTOMATICALLY SEND OR UPDATE THE ROSTER
# ============================================================

async def refresh_roster(guild):
    lock = refresh_locks.setdefault(guild.id, asyncio.Lock())

    async with lock:
        print(
            f"Starting roster refresh for {guild.name} "
            f"({guild.id})"
        )

        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
            except discord.NotFound:
                print(
                    f"ERROR: Channel {ROSTER_CHANNEL_ID} does not exist."
                )
                return
            except discord.Forbidden:
                print("ERROR: Bot cannot access the roster channel.")
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

        permissions = channel.permissions_for(guild.me)

        if not permissions.view_channel:
            print("ERROR: Bot needs View Channel permission.")
            return

        if not permissions.send_messages:
            print("ERROR: Bot needs Send Messages permission.")
            return

        if not permissions.read_message_history:
            print("ERROR: Bot needs Read Message History permission.")
            return

        # Build the Components V2 layout.
        try:
            view = await create_roster_view(guild)
        except Exception as error:
            print(
                f"ERROR building V2 roster: "
                f"{type(error).__name__}: {error}"
            )
            return

        state = load_state()
        guild_key = str(guild.id)
        saved_message_id = state.get(guild_key)
        roster_message = None

        # First, look for the saved message.
        if saved_message_id:
            try:
                candidate = await channel.fetch_message(
                    int(saved_message_id)
                )

                if is_roster_panel(candidate):
                    roster_message = candidate

            except discord.NotFound:
                print(
                    "Saved roster message was deleted; "
                    "searching for the old roster."
                )
            except (ValueError, TypeError):
                print("Saved roster message ID is invalid.")
            except discord.Forbidden:
                print("ERROR: Bot cannot read the saved roster message.")
                return
            except discord.HTTPException as error:
                print(f"ERROR fetching saved roster: {error}")
                return

        # Search history if the saved message is missing.
        if roster_message is None:
            roster_message = await find_existing_panel(channel)

        try:
            if roster_message is not None:
                # Clear legacy embed/content fields while replacing
                # the old message with the Components V2 layout.
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
                roster_message = await channel.send(view=view)

                print(
                    f"SUCCESS: New V2 roster sent "
                    f"to channel {channel.id}"
                )
                print(f"Roster message ID: {roster_message.id}")

            state[guild_key] = roster_message.id
            save_state(state)

        except discord.Forbidden:
            print(
                "ERROR: Discord denied permission to send or edit "
                "the V2 roster."
            )
        except discord.HTTPException as error:
            print(
                f"ERROR sending/editing V2 roster: "
                f"{error}"
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
            print(f"Automatically posting roster for {guild.name}...")
            await refresh_roster(guild)

        except Exception as error:
            print(
                f"STARTUP ROSTER ERROR: "
                f"{type(error).__name__}: {error}"
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
# Automatic startup does not depend on these commands.
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
        await ctx.send(
            "You need Administrator permission to use this command."
        )
    else:
        print(
            f"Refresh command error: "
            f"{type(error).__name__}: {error}"
        )
        await ctx.send("Roster refresh failed. Check Railway logs.")


@setup_roster_command.error
async def setup_roster_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "You need Administrator permission to use this command."
        )
    else:
        print(
            f"Setup command error: "
            f"{type(error).__name__}: {error}"
        )
        await ctx.send("Roster setup failed. Check Railway logs.")


# ============================================================
# START BOT
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to Railway Variables."
    )

bot.run(BOT_TOKEN)
