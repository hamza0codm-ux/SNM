
import os
import json
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

GUILD_ID = 1558112559125757992
ROSTER_CHANNEL_ID = 1558889366565167284

MESSAGE_FILE = "roster_message.json"
ACCENT_COLOUR = 0x5865F2

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# EMOJIS
# =========================

TEAM_EMOJI = "<:Team:1559130847972687932>"

OWNERSHIP_EMOJI = "<:SNM_Blue:1559131051442438214>"
BOARD_EMOJI = "<:SNM_red:1559131114524639242>"
MANAGEMENT_EMOJI = "<:SNM_Orange:1559131193205858305>"
STAFF_EMOJI = "<:SNM_Green:1559131246645346344>"

# =========================
# STAFF ROLES
# Order matters: highest role first.
# =========================

STAFF_ROLES = [
    {
        "id": 1477624642867826890,
        "name": "Founder",
        "target": 1,
        "section": "Ownership",
    },
    {
        "id": 1477623895799627859,
        "name": "Owner",
        "target": 2,
        "section": "Ownership",
    },
    {
        "id": 1477623895799627858,
        "name": "Co Owner",
        "target": 3,
        "section": "Ownership",
    },
    {
        "id": 1477623895799627856,
        "name": "Operations",
        "target": 4,
        "section": "Board Of Directors",
    },
    {
        "id": 1477623895799627855,
        "name": "Directors",
        "target": 8,
        "section": "Board Of Directors",
    },
    {
        "id": 1477623895799627851,
        "name": "General Management",
        "target": 4,
        "section": "Management",
    },
    {
        "id": 1477623895799627850,
        "name": "Management",
        "target": 13,
        "section": "Management",
    },
    {
        "id": 1477623895753494607,
        "name": "Admin",
        "target": 5,
        "section": "Staff",
    },
    {
        "id": 1477623895753494606,
        "name": "Staff",
        "target": 10,
        "section": "Staff",
    },
    {
        "id": 1477623895753494605,
        "name": "Trial Staff",
        "target": 10,
        "section": "Staff",
    },
]

# Department roles are displayed only beside members
# whose highest configured staff role is Management.
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
    {
        "name": "Ownership",
        "emoji": OWNERSHIP_EMOJI,
        "roles": ["Founder", "Owner", "Co Owner"],
    },
    {
        "name": "Board Of Directors",
        "emoji": BOARD_EMOJI,
        "roles": ["Operations", "Directors"],
    },
    {
        "name": "Management",
        "emoji": MANAGEMENT_EMOJI,
        "roles": ["General Management", "Management"],
    },
    {
        "name": "Staff",
        "emoji": STAFF_EMOJI,
        "roles": ["Admin", "Staff", "Trial Staff"],
    },
]

# =========================
# MESSAGE STORAGE
# =========================

def load_message_id():
    try:
        with open(MESSAGE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data.get("message_id")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_message_id(message_id):
    with open(MESSAGE_FILE, "w", encoding="utf-8") as file:
        json.dump({"message_id": message_id}, file)


# =========================
# MEMBER / ROLE HELPERS
# =========================

def get_highest_staff_role(member):
    """Return the highest configured staff role held by a member."""
    member_role_ids = {role.id for role in member.roles}

    for staff_role in STAFF_ROLES:
        if staff_role["id"] in member_role_ids:
            return staff_role

    return None


def get_department_mentions(member):
    """Return the member's department role mentions."""
    member_role_ids = {role.id for role in member.roles}
    mentions = []

    for role_id in DEPARTMENT_ROLE_IDS:
        if role_id in member_role_ids:
            mentions.append(f"<@&{role_id}>")

    if not mentions:
        return ""

    return " // " + " // ".join(mentions)


def get_role_members(guild, staff_role):
    """Count members exclusively under their highest configured staff role."""
    members = []

    for member in guild.members:
        if member.bot:
            continue

        highest_role = get_highest_staff_role(member)

        if highest_role and highest_role["id"] == staff_role["id"]:
            members.append(member)

    return sorted(members, key=lambda member: member.display_name.casefold())


def build_role_text(guild, staff_role):
    """Build one compact role entry."""
    role_id = staff_role["id"]
    target = staff_role["target"]
    members = get_role_members(guild, staff_role)

    lines = [f"<@&{role_id}> — {len(members)}/{target}"]

    if not members:
        lines.append("- **N/A**")
        return "\n".join(lines)

    for member in members:
        line = f"- {member.mention}"

        # Department mentions only appear for the Management role.
        if staff_role["name"] == "Management":
            line += get_department_mentions(member)

        lines.append(line)

    return "\n".join(lines)


# =========================
# COMPONENTS V2 ROSTER
# =========================

def build_roster_view(guild):
    view = discord.ui.LayoutView(timeout=None)

    # Roster title
    title_container = discord.ui.Container(
        accent_colour=discord.Colour(ACCENT_COLOUR)
    )
    title_container.add_item(
        discord.ui.TextDisplay(
            f"**__{TEAM_EMOJI} | SNM Staff Roster__**"
        )
    )
    view.add_item(title_container)

    # Keep each section separate, with visible dividers.
    for section in SECTIONS:
        view.add_item(discord.ui.Separator(visible=True))

        container = discord.ui.Container(
            accent_colour=discord.Colour(ACCENT_COLOUR)
        )

        container.add_item(
            discord.ui.TextDisplay(
                f"**{section['emoji']} __{section['name']}__**"
            )
        )

        container.add_item(discord.ui.Separator(visible=True))

        section_roles = [
            role for role in STAFF_ROLES
            if role["name"] in section["roles"]
        ]

        for index, staff_role in enumerate(section_roles):
            container.add_item(
                discord.ui.TextDisplay(
                    build_role_text(guild, staff_role)
                )
            )

            # Small divider between role entries, not extra blank lines.
            if index < len(section_roles) - 1:
                container.add_item(
                    discord.ui.Separator(visible=True)
                )

        view.add_item(container)

    return view


# =========================
# REFRESH / UPDATE LOGIC
# =========================

refresh_lock = asyncio.Lock()
refresh_task = None


async def refresh_roster():
    async with refresh_lock:
        guild = bot.get_guild(GUILD_ID)

        if guild is None:
            logging.error("Configured server was not found.")
            return

        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
            except discord.HTTPException:
                logging.exception("Could not find the roster channel.")
                return

        # Try to load the full member list for accurate counts.
        try:
            await asyncio.wait_for(
                guild.chunk(cache=True),
                timeout=30,
            )
        except asyncio.TimeoutError:
            logging.warning(
                "Member-cache request timed out. "
                "Counts may be incomplete until members are cached."
            )
        except discord.HTTPException:
            logging.exception("Could not refresh the server member cache.")

        view = build_roster_view(guild)
        message_id = load_message_id()
        roster_message = None

        if message_id:
            try:
                roster_message = await channel.fetch_message(int(message_id))
            except (discord.NotFound, discord.HTTPException, ValueError):
                roster_message = None

        try:
            if roster_message is not None:
                # Components V2 messages must be edited using the view,
                # not by mixing traditional embed arguments.
                if roster_message.flags.is_components_v2:
                    await roster_message.edit(view=view)
                    logging.info("Roster updated successfully.")
                    return

                # Replace an older non-Components-V2 roster.
                await roster_message.delete()

            new_message = await channel.send(view=view)
            save_message_id(new_message.id)
            logging.info("Roster posted successfully.")

        except discord.Forbidden:
            logging.exception(
                "Missing channel permissions. Check View Channel, "
                "Send Messages, Read Message History and required intents."
            )
        except discord.HTTPException:
            logging.exception("Discord rejected the roster update.")
        except Exception:
            logging.exception("Unexpected error while updating the roster.")


async def delayed_refresh():
    await asyncio.sleep(1)
    await refresh_roster()


def schedule_refresh():
    global refresh_task

    if refresh_task and not refresh_task.done():
        refresh_task.cancel()

    refresh_task = asyncio.create_task(delayed_refresh())


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    logging.info("Logged in as %s (%s)", bot.user, bot.user.id)
    logging.info("Automatically checking the staff roster...")
    schedule_refresh()


@bot.event
async def on_member_join(member):
    if member.guild.id == GUILD_ID:
        schedule_refresh()


@bot.event
async def on_member_remove(member):
    if member.guild.id == GUILD_ID:
        schedule_refresh()


@bot.event
async def on_member_update(before, after):
    if after.guild.id != GUILD_ID:
        return

    if before.roles != after.roles or before.nick != after.nick:
        schedule_refresh()


@bot.event
async def on_guild_role_update(before, after):
    if after.guild.id == GUILD_ID:
        schedule_refresh()


@bot.event
async def on_guild_role_delete(role):
    if role.guild.id == GUILD_ID:
        schedule_refresh()


@bot.event
async def on_message_delete(message):
    if message.channel.id != ROSTER_CHANNEL_ID:
        return

    saved_id = load_message_id()

    if saved_id and message.id == int(saved_id):
        logging.info("Roster message was deleted; recreating it.")
        schedule_refresh()


# =========================
# OPTIONAL MANUAL REFRESH
# =========================

@bot.command(name="rosterrefresh")
@commands.has_permissions(administrator=True)
async def roster_refresh_command(ctx):
    await refresh_roster()
    await ctx.reply("Roster refresh requested.", delete_after=5)


@roster_refresh_command.error
async def roster_refresh_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(
            "You need Administrator permission to use this command.",
            delete_after=5,
        )


# =========================
# START BOT
# =========================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add it to your Railway Variables."
    )

bot.run(BOT_TOKEN)
