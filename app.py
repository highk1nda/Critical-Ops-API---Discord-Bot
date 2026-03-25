import io
import logging
import random
import asyncio
import contextlib

import aiohttp
import discord
from discord.ext import commands

from config.settings import DISCORD_TOKEN
from config.constants import (
    STATUS_CHANNEL_ID,
    ADMIN_ROLE_ID,
    UKRY_ROLE_ID,
    ROLE_MAP,
    COMMAND_PREFIX,
    LOG_FILE,
    SYRNYK_RESPONSE_CHANCE,
    MSG_NOT_ADMIN,
    MSG_SHUTTING_DOWN,
    MSG_PROFILE_NOT_FOUND,
)
from core.api import ProfileApiClient
from core.stats import parse_profile
from core.smurf import calculate_smurf_score
from rendering.stats_card import render_stats_card
from utils.executor import render_image_async
from bot.profile import build_profile_embed, ProfileStatsView
from bot.roles import build_status_embed, VerificationView, handle_reaction_add, handle_reaction_remove

# ============================================================
# LOGGING
# ============================================================

handler = logging.FileHandler(filename=LOG_FILE, encoding="utf-8", mode="w")

# ============================================================
# INTENTS
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# ============================================================
# BOT SUBCLASS
# ============================================================

class Bot(commands.Bot):

    def __init__(self) -> None:
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents)
        self._http_session: aiohttp.ClientSession | None = None
        self.api_client: ProfileApiClient | None = None

    async def setup_hook(self) -> None:
        self._http_session = aiohttp.ClientSession()
        self.api_client = ProfileApiClient(self._http_session)
        self.add_view(VerificationView(ADMIN_ROLE_ID, UKRY_ROLE_ID))

    async def close(self) -> None:
        print("Shutting down gracefully...")

        with contextlib.suppress(Exception):
            channel = self.get_channel(STATUS_CHANNEL_ID)
            if channel:
                await asyncio.wait_for(
                    channel.send(embed=build_status_embed("stopped")),
                    timeout=3,
                )

        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

        await super().close()
        print("Shutdown complete.")


bot = Bot()


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_raw_reaction_add(payload):
    await handle_reaction_add(bot, payload, ROLE_MAP, ADMIN_ROLE_ID, UKRY_ROLE_ID)


@bot.event
async def on_raw_reaction_remove(payload):
    await handle_reaction_remove(bot, payload, ROLE_MAP)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "syrnyk" in message.content.lower():
        if random.random() < SYRNYK_RESPONSE_CHANCE:
            await message.channel.send(f"{message.author.mention}, wanna get banned?")

    await bot.process_commands(message)


# ============================================================
# SLASH COMMANDS
# ============================================================

@bot.tree.command(name="search", description="Search player profile")
async def search(interaction: discord.Interaction, name: str) -> None:
    await interaction.response.defer()

    raw_profile = await bot.api_client.fetch_profile(name)

    if not raw_profile:
        await interaction.followup.send(MSG_PROFILE_NOT_FOUND)
        return

    parsed_profile = parse_profile(raw_profile)
    smurf_score = calculate_smurf_score(parsed_profile)

    render_data = {**parsed_profile, "smurf_score": smurf_score, "username": name}
    image = await render_image_async(render_stats_card, render_data)

    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True)
    buf.seek(0)
    file = discord.File(buf, filename="stats.png")

    embed = build_profile_embed(name, parsed_profile, smurf_score)
    view = ProfileStatsView(name, parsed_profile, smurf_score)

    await interaction.followup.send(embed=embed, file=file, view=view)


@bot.tree.command(name="stop", description="Gracefully shut down the bot")
async def stop(interaction: discord.Interaction) -> None:
    is_admin = any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

    if not is_admin:
        await interaction.response.send_message(MSG_NOT_ADMIN, ephemeral=True)
        return

    await interaction.response.send_message(MSG_SHUTTING_DOWN, ephemeral=True)
    asyncio.get_event_loop().create_task(bot.close())


# ============================================================
# READY EVENT
# ============================================================

@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if channel:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(
                channel.send(embed=build_status_embed("started")),
                timeout=3,
            )


# ============================================================
# MAIN
# ============================================================

async def main() -> None:
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    logging.basicConfig(handlers=[handler], level=logging.INFO)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
