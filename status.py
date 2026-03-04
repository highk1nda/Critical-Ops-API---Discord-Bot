# status.py

import discord
from datetime import datetime
from zoneinfo import ZoneInfo


def build_status_embed(status: str) -> discord.Embed:
    # Build bot status embed

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

    embed.set_footer(text="Timezone: Europe/Berlin mala")

    return embed
