
import os
import json
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = 1558112559125757992
ROSTER_CHANNEL_ID = 1558889366565167284
MESSAGE_FILE = "roster_message.json"

# CHANGE YOUR EMOJIS HERE
TEAM_EMOJI = "<:Team:1559130847972687932>"
OWNERSHIP_EMOJI = "<:SNM_Blue:1559131051442438214>"
LEADERSHIP_EMOJI = "<:SNM_red:1559131114524639242>"
MANAGEMENT_EMOJI = "<:SNM_Orange:1559131193205858305>"
STAFF_EMOJI = "<:SNM_Green:1559131246645346344>"

# =========================
# STAFF ROLES
# Highest configured role first
# =========================

STAFF_ROLES = [
    {"id": 1558896822410547210, "name": "Founder", "target": 1},
    {"id": 1558896894678278164, "name": "Owner", "target": 2},
    {"id": 1558896918443327589, "name": "Co Owner", "target": 3},
    {"id": 1558896966459592704, "name": "Operations", "target": 4},
    {"id": 1558897001406406741, "name": "Directors", "target": 8},
    {"id": 1558897060441235558, "name": "General Management", "target": 4},
    {"id": 1558897026568028273, "name": "Management", "target": 13},
    {"id": 1558897520606974112, "name": "Admin", "target": 5},
    {"id": 1558897546242429100, "name": "Staff", "target": 10},
    {"id": 1558897577976528957, "name": "Trial Staff", "target": 10},
]

# Departments appear next to Management members only.
# There is no Departments list at the bottom.

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
        "name": "Ownership Team",
        "emoji": OWNERSHIP_EMOJI,
        "roles": ["Founder", "Owner", "Co Owner"],
    },
    {
        "name": "Leadership Team",
        "emoji": LEADERSHIP_EMOJI,
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
# BOT SETUP
# =========================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

refresh_lock = asyncio.Lock()
refresh_task = None


# =========================
# SAVE MESSAGE ID
# =========================

def load_message_id():
    try:
        with open(MESSAGE_FILE, "r", encoding="utf-8") as file:
            return json.load(file).get("message_id")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_message_id(message_id):
    with open(MESSAGE_FILE, "w", encoding="utf-8") as file:
        json.dump({"message_id": message_id}, file)


# =========================
# MEMBER HELPERS
# =========================

def highest_staff_role(member):
    member_role_ids = {role.id for role in member.roles}

    for staff_role in STAFF_ROLES:
        if staff_role["id"] in member_role_ids:
            return staff_role

    return None


def members_for_role(guild, staff_role):
    members = []

    for member in guild.members:
        if member.bot:
            continue

        highest = highest_staff_role(member)

        if highest and highest["id"] == staff_role["id"]:
            members.append(member)

    return sorted(
        members,
        key=lambda member: member.display_name.casefold()
    )


def department_mentions(member):
    member_role_ids = {role.id for role in member.roles}

    departments = [
        f"<@&{role_id}>"
        for role_id in DEPARTMENT_ROLE_IDS
        if role_id in member_role_ids
    ]

    return " // " + " // ".join(departments) if departments else ""


def build_role_entry(guild, staff_role):
    members = members_for_role(guild, staff_role)

    lines = [
        f"<@&{staff_role['id']}> — "
        f"{len(members)}/{staff_role['target']}"
    ]

    if not members:
        lines.append("- **N/A**")
    else:
        for member in members:
            line = f"- {member.mention}"

            if staff_role["name"] == "Management":
                line += department_mentions(member)

            lines.append(line)

    return "\n".join(lines)


# =========================
# COMPONENTS V2 HELPERS
# =========================

def add_text(view, content):
    """Add text displays while respecting Discord's size limits."""
    max_length = 3900
    content = str(content)

    while content:
        if len(content) <= max_length:
            view.add_item(discord.ui.TextDisplay(content))
            break

        split_at = content.rfind("\n", 0, max_length)

        if split_at <= 0:
            split_at = max_length

        view.add_item(
            discord.ui.TextDisplay(content[:split_at])
        )

        content = content[split_at:].lstrip("\n")


def add_divider(view):
    """Add a real Discord Divider/Separator component."""
    view.add_item(
        discord.ui.Separator(
            visible=True,
            spacing=discord.SeparatorSpacing.large,
        )
    )


# =========================
# BUILD ROSTER
# =========================

def build_roster_view(guild):
    view = discord.ui.LayoutView(timeout=None)

    add_text(view, f"# {TEAM_EMOJI} | SNM Staff Roster")

    for section_index, section in enumerate(SECTIONS):
        if section_index > 0:
            add_divider(view)

        add_text(
            view,
            f"## {section['emoji']} {section['name']}"
        )

        for role_name in section["roles"]:
            staff_role = next(
                role for role in STAFF_ROLES
                if role["name"] == role_name
            )

            add_text(
                view,
                build_role_entry(guild, staff_role)
            )

    # No Departments section at the bottom.
    return view


# =========================
# FIND EXISTING MESSAGE
# =========================

async def find_existing_message(channel):
    # First try the saved message ID.
    message_id = load_message_id()

    if message_id:
        try:
            return await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.HTTPException, ValueError):
            logging.warning(
                "Saved roster message not found; searching channel history."
            )

    # If Railway lost the ID file, recover the existing roster
    # rather than automatically creating another message.
    try:
        async for message in channel.history(limit=100):
            if bot.user is None or message.author.id != bot.user.id:
                continue

            # Find a previous Components V2 roster.
            if message.flags.is_components_v2:
                save_message_id(message.id)
                return message

            # Also recognise the old classic embed roster.
            if any(
                embed.title and "SNM Staff Roster" in embed.title
                for embed in message.embeds
            ):
                save_message_id(message.id)
                return message

    except discord.HTTPException:
        logging.exception("Could not search channel history.")

    return None


# =========================
# REFRESH EXISTING MESSAGE
# =========================

async def refresh_roster():
    async with refresh_lock:
        guild = bot.get_guild(GUILD_ID)

        if guild is None:
            logging.error("Server not found. Check GUILD_ID.")
            return

        channel = guild.get_channel(ROSTER_CHANNEL_ID)

        if channel is None:
            try:
                channel = await bot.fetch_channel(ROSTER_CHANNEL_ID)
            except discord.HTTPException:
                logging.exception("Roster channel could not be found.")
                return

        try:
            await asyncio.wait_for(
                guild.chunk(cache=True),
                timeout=30,
            )
        except asyncio.TimeoutError:
            logging.warning(
                "Member cache timed out; roster counts may be incomplete."
            )
        except discord.HTTPException:
            logging.exception("Could not load the member cache.")

        view = build_roster_view(guild)
        old_message = await find_existing_message(channel)

        # Display mentions without repeatedly notifying staff on every edit.
        allowed_mentions = discord.AllowedMentions.none()

        try:
            if old_message:
                if old_message.flags.is_components_v2:
                    # Edit the same Components V2 message.
                    await old_message.edit(
                        content=None,
                        embeds=[],
                        attachments=[],
                        view=view,
                        allowed_mentions=allowed_mentions,
                    )

                    logging.info(
                        "Roster updated in the existing message: %s",
                        old_message.id,
                    )
                    return

                # A classic embed cannot be converted into Components V2
                # by editing. Replace it once with the new layout.
                logging.info(
                    "Replacing the old classic embed with Components V2."
                )

                try:
                    await old_message.delete()
                except discord.NotFound:
                    pass

            new_message = await channel.send(
                view=view,
                allowed_mentions=allowed_mentions,
            )

            save_message_id(new_message.id)

            logging.info(
                "Roster created. Message ID: %s",
                new_message.id,
            )

        except discord.Forbidden:
            logging.exception(
                "Missing permissions to read history, send, edit, or delete."
            )

        except discord.HTTPException:
            logging.exception("Discord rejected the roster update.")

        except Exception:
            logging.exception("Unexpected roster refresh error.")


async def delayed_refresh():
    await asyncio.sleep(2)
    await refresh_roster()


def schedule_refresh():
    global refresh_task

    if refresh_task and not refresh_task.done():
        refresh_task.cancel()

    refresh_task = asyncio.create_task(delayed_refresh())


# =========================
# AUTOMATIC UPDATES
# =========================

@bot.event
async def on_ready():
    logging.info("Logged in as %s (%s)", bot.user, bot.user.id)
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


# No on_message_delete handler: avoids deletion/recreation loops.


# =========================
# MANUAL REFRESH COMMAND
# =========================

@bot.command(name="rosterrefresh")
@commands.has_permissions(administrator=True)
async def roster_refresh_command(ctx):
    await refresh_roster()
    await ctx.reply("Roster refreshed.", delete_after=5)


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
        "BOT_TOKEN is missing from your Railway environment variables."
    )

bot.run(BOT_TOKEN)
