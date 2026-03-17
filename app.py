import os
import logging
import random
import asyncio
import contextlib

import discord
from discord.ext import commands
from dotenv import load_dotenv

from status import build_status_embed
from stats import get_profile_info, build_main_embed, ProfileStatsView, close_session
import roles

# ENV SETUP

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

STATUS_CHANNEL_ID = 1477285735655538709
ADMIN_ROLE_ID = 1372986279159005265

ROLE_MAP = {
    "⚔": 1436468159061168231,
    "♾": 1411844893705240686,
    "☢": 1407487106271412274,
}

# LOGGING

handler = logging.FileHandler(
    filename="discord.log",
    encoding="utf-8",
    mode="w"
)

# INTENTS

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# BOT SUBCLASS

class Bot(commands.Bot):

    def __init__(self):
        super().__init__(command_prefix="syr", intents=intents)

    async def setup_hook(self):
        self.add_view(
            roles.VerificationView(
                ADMIN_ROLE_ID,
                1407487106271412274
            )
        )

    async def close(self):
        print("Shutting down gracefully...")

        with contextlib.suppress(Exception):
            channel = self.get_channel(STATUS_CHANNEL_ID)
            if channel:
                await asyncio.wait_for(
                    channel.send(embed=build_status_embed("stopped")),
                    timeout=3
                )

        await close_session()
        await super().close()
        print("Shutdown complete.")


bot = Bot()


# EVENTS

@bot.event
async def on_raw_reaction_add(payload):
    await roles.handle_reaction_add(
        bot,
        payload,
        ROLE_MAP,
        ADMIN_ROLE_ID,
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

    await interaction.followup.send(embed=embed, view=view)


# SLASH COMMAND /stop

@bot.tree.command(name="stop", description="Gracefully shut down the bot")
async def stop(interaction: discord.Interaction):
    is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

    if not is_admin:
        await interaction.response.send_message("You are not admin.", ephemeral=True)
        return

    # Acknowledge immediately — close() will send the embed itself
    await interaction.response.send_message("Shutting down...", ephemeral=True)

    # Schedule close() on the running loop without blocking the interaction
    asyncio.get_event_loop().create_task(bot.close())


# READY EVENT

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if channel:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(
                channel.send(embed=build_status_embed("started")),
                timeout=3
            )


# MAIN

async def main():
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    logging.basicConfig(handlers=[handler], level=logging.INFO)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass