import os
import logging
import random
import signal
import asyncio
import contextlib

import discord
from discord.ext import commands
from dotenv import load_dotenv

from status import build_status_embed
from stats import get_profile_info, build_main_embed, ProfileStatsView
import roles

# ENV SETUP


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

STATUS_CHANNEL_ID = 1477285735655538709

ROLE_MAP = {
    "⚔": 1436468159061168231,
    "♾": 1411844893060686,
    "☢": 1407487106271412274,
}

# LOGGING


handler = logging.FileHandler(
    filename="discord.log",
    encoding="utf-8",
    mode="w"
)

# INTENTS (memory opimized)


intents = discord.Intents.default()
intents.message_content = True
intents.members = False  # Disable full member cache

bot = commands.Bot(
    command_prefix="syr",
    intents=intents,
    member_cache_flags=discord.MemberCacheFlags.none()
)


# EVENTS


@bot.event
async def on_raw_reaction_add(payload):
    await roles.handle_reaction_add(
        bot,
        payload,
        ROLE_MAP,
        1372986279159005265,
        1407487106271412274
    )


@bot.event
async def on_raw_reaction_remove(payload):
    await roles.handle_reaction_remove(bot, payload, ROLE_MAP)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "syrnyk" in message.content.lower():
        if random.random() < 0.10:
            await message.channel.send(
                f"{message.author.mention}, wanna get banned?"
            )

    await bot.process_commands(message)


# SLASH COMMAND /search


@bot.tree.command(name="search", description="Search player profile")
async def search(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    profile = await get_profile_info(name)

    if not profile:
        await interaction.followup.send("Profile not found.")
        return

    embed = build_main_embed(name, profile)
    view = ProfileStatsView(name, profile)

    await interaction.followup.send(
        embed=embed,
        view=view
    )


# READY EVENT


@bot.event
async def on_ready():
    bot.add_view(
        roles.VerificationView(
            1372986279159005265,
            1407487106271412274
        )
    )

    await bot.tree.sync()

    print(f"Logged in as {bot.user}")

    channel = bot.get_channel(STATUS_CHANNEL_ID)

    if channel:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(
                channel.send(embed=build_status_embed("started")),
                timeout=3
            )


# SHUTDOWN


def shutdown_handler(sig, frame):
    print(f"Received exit signal {sig}")

    async def shutdown():

        try:
            channel = bot.get_channel(STATUS_CHANNEL_ID)

            if channel:
                await asyncio.wait_for(
                    channel.send(embed=build_status_embed("stopped")),
                    timeout=2
                )
        except Exception:
            pass

        try:
            await bot.close()
        except Exception:
            pass

    loop = asyncio.get_event_loop()

    if loop.is_running():
        asyncio.create_task(shutdown())
    else:
        loop.run_until_complete(shutdown())


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# RUN BOT


if __name__ == "__main__":
    try:
        bot.run(
            TOKEN,
            log_handler=handler,
            log_level=logging.INFO
        )
    except KeyboardInterrupt:
        pass
