"""
bot/profile.py

Discord embed builder and interactive stats view — combined in one module.
"""

from __future__ import annotations

import io

import discord

from config.constants import EMBED_FOOTER, VIEW_TIMEOUT
from rendering.stats_card import render_stats_card
from utils.executor import render_image_async


# ── Embed ─────────────────────────────────────────────────────────────────────

def build_profile_embed(username: str, parsed_profile: dict, smurf_score: float) -> discord.Embed:
    """Build the stats embed from pre-parsed profile data and a smurf score."""
    current = parsed_profile["current"]
    ranked = parsed_profile["ranked"]
    non_ranked = parsed_profile["non_ranked"]
    most_played = parsed_profile.get("most_played_season")

    embed = discord.Embed(
        title=f"📊 Profile Stats — {username}",
        color=discord.Color.orange(),
    )

    embed.add_field(name="Clan", value=parsed_profile["clan"], inline=False)
    embed.add_field(name="Smurf Detection %", value=f"{smurf_score}%", inline=False)

    embed.add_field(
        name="Current Ranked Stats",
        value=(
            f"K: {current['kills']} | W: {current['wins']}\n"
            f"D: {current['deaths']} | L: {current['losses']}\n"
            f"KD: {current['kd']} | WinRate: {current['winrate']}%\n"
            f"Played Games: {current['games']}"
        ),
        inline=False,
    )

    embed.add_field(
        name="Overall Ranked",
        value=(
            f"K: {ranked['kills']} | W: {ranked['wins']}\n"
            f"D: {ranked['deaths']} | L: {ranked['losses']}\n"
            f"KD: {ranked['kd']} | WinRate: {ranked['winrate']}%\n"
            f"Played Games: {ranked['total_games']}"
        ),
        inline=False,
    )

    if most_played:
        embed.add_field(
            name="Most Played Season",
            value=f"Season {most_played['season']}, {most_played['percentage']}%",
            inline=False,
        )

    embed.add_field(
        name="Casual + Custom Combined",
        value=f"Total Kills: {non_ranked['kills']} | K/D: {non_ranked['kd']}",
        inline=False,
    )

    embed.set_footer(text=EMBED_FOOTER)
    embed.set_image(url="attachment://stats.png")

    return embed


# ── View ──────────────────────────────────────────────────────────────────────

class ProfileStatsView(discord.ui.View):

    def __init__(self, username: str, parsed_profile: dict, smurf_score: float) -> None:
        super().__init__(timeout=VIEW_TIMEOUT)
        self.username = username
        self.parsed_profile = parsed_profile
        self.smurf_score = smurf_score

    async def on_timeout(self) -> None:
        self.stop()

    @discord.ui.button(label="Summary", style=discord.ButtonStyle.secondary)
    async def summary(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        render_data = {**self.parsed_profile, "smurf_score": self.smurf_score, "username": self.username}
        image = await render_image_async(render_stats_card, render_data)

        buf = io.BytesIO()
        image.save(buf, "PNG", optimize=True)
        buf.seek(0)
        file = discord.File(buf, filename="stats.png")

        embed = build_profile_embed(self.username, self.parsed_profile, self.smurf_score)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
