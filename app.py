import discord
from discord.ext import commands
from discord import app_commands
import logging
from dotenv import load_dotenv
import os
import aiohttp
import asyncio
import signal
from datetime import datetime
from zoneinfo import ZoneInfo
import random

# ENVIRONMENT


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # Not leaking, sowwy :)

# LOGGING


handler = logging.FileHandler(
    filename="discord.log",
    encoding="utf-8",
    mode="w"
)

# BOT CONFIG


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="syr", intents=intents)

import signal


async def shutdown_bot():
    channel = bot.get_channel(STATUS_CHANNEL_ID)

    if channel:
        try:
            await channel.send(embed=build_status_embed("stopped"))
        except Exception:
            pass

    await bot.close()


def signal_handler(sig, frame):
    print(f"Received exit signal {sig}")

    loop = asyncio.get_event_loop()

    if loop.is_running():
        asyncio.create_task(shutdown_bot())
    else:
        loop.run_until_complete(shutdown_bot())


# Register signals
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# CONFIGURATION


REACTION_MESSAGE_ID = 1477285069432422483
STATUS_CHANNEL_ID = 1477285735655538709

ADMIN_ROLE_ID = 1372986279159005265
UKRY_ROLE_ID = 1407487106271412274

API_URL = "https://1-60-0.prod.copsapi.criticalforce.fi/api/public/profile"

ROLE_MAP = {
    "⚔": 1436468159061168231,
    "♾": 1411844893705240686,
    "☢": UKRY_ROLE_ID,
}


# STAT HELPERS


def calculate_kd(k, d):
    return round(k / d, 2) if d > 0 else float(k)


def calculate_winrate(w, l):
    total = w + l
    return round((w / total) * 100, 2) if total > 0 else 0.0


def calculate_smurf_percentage(kd, total_games, season_count):
    score = 0

    if kd >= 2.5:
        score += 40
    elif kd >= 2.0:
        score += 25

    if total_games < 150 and kd >= 2.0:
        score += 25

    if season_count == 1:
        score += 20

    return min(score, 100)


# API FETCH (ASYNC)


async def get_profile_info(username: str):
    try:
        async with aiohttp.ClientSession() as session:

            url = f"{API_URL}?usernames={username}"

            async with session.get(url, timeout=10) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                if not isinstance(data, list) or not data:
                    return None

                return data[0]

    except Exception:
        return None


# STATUS EMBED BUILDER


def build_status_embed(status: str):
    berlin_time = datetime.now(ZoneInfo("Europe/Berlin"))

    if status == "started":
        color = discord.Color.green()
        title = "🟢 Bot Started"
        description = "The bot is online fellas"
    else:
        color = discord.Color.red()
        title = "🔴 Bot Stopped"
        description = "The bot has been shut down.🥺"

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=berlin_time
    )

    embed.set_footer(text="Timezone: Europe/Berlin babe")
    return embed


# VERIFICATION VIEW


class VerificationView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        custom_id="ukry_approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "You are not admin.",
                ephemeral=True
            )
            return

        member_id = int(interaction.channel.name.split("-")[-1])
        member = interaction.guild.get_member(member_id)
        role = interaction.guild.get_role(UKRY_ROLE_ID)

        if member and role:
            await member.add_roles(role)

        await interaction.response.send_message("Approved. Role assigned.")
        await interaction.channel.delete()

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.red,
        custom_id="ukry_decline"
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message(
                "You are not admin.",
                ephemeral=True
            )
            return

        await interaction.response.send_message("Declined.")
        await interaction.channel.delete()


# EMBED REPORT BUILDER


def build_profile_embed(username, profile):
    stats = profile.get("stats", {})

    ranked_totals = {"k": 0, "d": 0, "w": 0, "l": 0}

    current_ranked = None
    current_season_number = -1
    seasons_data = []

    for season in stats.get("seasonal_stats", []):

        ranked = season.get("ranked", {})
        games = ranked.get("w", 0) + ranked.get("l", 0)

        if games > 0:

            season_number = season.get("season", 0)

            ranked_totals["k"] += ranked.get("k", 0)
            ranked_totals["d"] += ranked.get("d", 0)
            ranked_totals["w"] += ranked.get("w", 0)
            ranked_totals["l"] += ranked.get("l", 0)

            seasons_data.append((season_number, games))

            if season_number > current_season_number:
                current_season_number = season_number
                current_ranked = ranked

    k = ranked_totals["k"]
    d = ranked_totals["d"]
    w = ranked_totals["w"]
    l = ranked_totals["l"]

    kd = calculate_kd(k, d)
    winrate = calculate_winrate(w, l)

    total_ranked_games = w + l

    if current_ranked:
        c_k = current_ranked.get("k", 0)
        c_d = current_ranked.get("d", 0)
        c_w = current_ranked.get("w", 0)
        c_l = current_ranked.get("l", 0)

        c_kd = calculate_kd(c_k, c_d)
        c_winrate = calculate_winrate(c_w, c_l)

    else:
        c_k = c_d = c_w = c_l = c_kd = c_winrate = 0

    season_percentages = []

    for season_number, games in seasons_data:
        pct = round((games / total_ranked_games) * 100, 2) if total_ranked_games > 0 else 0
        season_percentages.append((season_number, pct))

    most_played = ("", 0)

    for season, pct in season_percentages:
        if pct > most_played[1]:
            most_played = (season, pct)

    casual_k = casual_d = custom_k = custom_d = 0

    for season in stats.get("seasonal_stats", []):
        casual = season.get("casual", {})
        custom = season.get("custom", {})
        custom_lobbies = season.get("custom_lobbies", {})

        casual_k += casual.get("k", 0)
        casual_d += casual.get("d", 0)

        custom_k += custom.get("k", 0)
        custom_d += custom.get("d", 0)

        custom_k += custom_lobbies.get("k", 0)
        custom_d += custom_lobbies.get("d", 0)

    total_k = casual_k + custom_k
    total_d = casual_d + custom_d

    casual_pct = round((casual_k / total_k) * 100, 2) if total_k > 0 else 0
    custom_pct = round((custom_k / total_k) * 100, 2) if total_k > 0 else 0

    total_kd = calculate_kd(total_k, total_d)
    casual_kd = calculate_kd(casual_k, casual_d)
    custom_kd = calculate_kd(custom_k, custom_d)

    smurf_pct = calculate_smurf_percentage(
        kd,
        total_ranked_games,
        len(season_percentages)
    )

    embed = discord.Embed(
        title=f"📊 This dude's ({username}) stats",
        color=discord.Color.from_rgb(255, 165, 0)
    )

    embed.add_field(
        name="Smurf Detector",
        value=f"{smurf_pct}%",
        inline=False
    )

    embed.add_field(
        name="Overall Ranked Stats",
        value=(
            f"K/D: {kd}\n"
            f"K: {k}\n"
            f"D: {d}\n"
            f"W: {w}\n"
            f"L: {l}\n"
            f"W/L%: {winrate}%"
        ),
        inline=False
    )

    embed.add_field(
        name="Current Ranked Season Stats",
        value=(
            f"K/D: {c_kd}\n"
            f"K: {c_k}\n"
            f"D: {c_d}\n"
            f"W: {c_w}\n"
            f"L: {c_l}\n"
            f"W/L%: {c_winrate}%"
        ),
        inline=False
    )

    season_text = ""

    for season, pct in sorted(season_percentages):
        season_text += f"Season {season}: {pct}%\n"

    if season_text:
        embed.add_field(
            name="Played in Seasons",
            value=season_text.strip(),
            inline=False
        )

    if most_played[0] != "":
        embed.add_field(
            name="Most Played Season",
            value=f"Season {most_played[0]} ({most_played[1]}%)",
            inline=False
        )

    embed.add_field(
        name="Casual + Custom Combined",
        value=(
            f"Total Kills: {total_k} | K/D: {total_kd}\n"
            f"Casual Kills: {casual_k} ({casual_pct}%) | K/D: {casual_kd}\n"
            f"Custom Kills: {custom_k} ({custom_pct}%) | K/D: {custom_kd}"
        ),
        inline=False
    )

    embed.set_footer(text="cwazy stats bot")

    return embed


# REACTION ROLE SYSTEM


@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        return

    emoji = str(payload.emoji)

    if emoji == "☢":

        admin_role = guild.get_role(ADMIN_ROLE_ID)

        existing_channel = discord.utils.get(
            guild.channels,
            name=f"ukry-verification-{member.id}"
        )

        if existing_channel:
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=f"ukry-verification-{member.id}",
            overwrites=overwrites
        )

        await channel.send(
            f"{member.mention} requested **Ukry clan membership**.",
            view=VerificationView()
        )

        return

    if emoji in ROLE_MAP:
        role = guild.get_role(ROLE_MAP[emoji])
        if role:
            await member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        return

    emoji = str(payload.emoji)

    if emoji in ROLE_MAP and emoji != "☢":
        role = guild.get_role(ROLE_MAP[emoji])
        if role:
            await member.remove_roles(role)


# MESSAGE HANDLER


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "syrnyk" in message.content.lower():
        if random.random() < 0.10:
            await message.channel.send(
                f"{message.author.mention}, wanna get banned?"
            )

    await bot.process_commands(message)


# SLASH SEARCH COMMAND


@bot.tree.command(name="search", description="Search player profile")
async def search(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    profile = await get_profile_info(name)

    if not profile:
        await interaction.followup.send("Profile not found or API error.")
        return

    embed = build_profile_embed(name, profile)

    await interaction.followup.send(embed=embed)


# READY EVENT


@bot.event
async def on_ready():
    bot.add_view(VerificationView())

    await bot.tree.sync()

    print(f"Logged in as {bot.user}")

    channel = bot.get_channel(STATUS_CHANNEL_ID)

    if channel:
        await channel.send(embed=build_status_embed("started"))


# RUN BOT


bot.run(TOKEN, log_handler=handler, log_level=logging.INFO)
