"""
bot/roles.py

Discord role management (reaction roles + clan verification) and bot status embeds.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from config.constants import (
    REACTION_MESSAGE_ID,
    STATUS_TIMEZONE,
    STATUS_FOOTER,
    STATUS_STARTED_TITLE,
    STATUS_STARTED_DESC,
    STATUS_STOPPED_TITLE,
    STATUS_STOPPED_DESC,
    MSG_NOT_ADMIN,
    MSG_APPROVED,
    MSG_DECLINED,
)


# ── Status embed ──────────────────────────────────────────────────────────────

def build_status_embed(status: str) -> discord.Embed:
    berlin_time = datetime.now(ZoneInfo(STATUS_TIMEZONE))

    if status == "started":
        color = discord.Color.green()
        title = STATUS_STARTED_TITLE
        description = STATUS_STARTED_DESC
    else:
        color = discord.Color.red()
        title = STATUS_STOPPED_TITLE
        description = STATUS_STOPPED_DESC

    embed = discord.Embed(title=title, description=description, color=color, timestamp=berlin_time)
    embed.set_footer(text=STATUS_FOOTER)
    return embed


# ── Verification view ─────────────────────────────────────────────────────────

class VerificationView(discord.ui.View):

    def __init__(self, admin_role_id: int, ukry_role_id: int):
        super().__init__(timeout=None)
        self.admin_role_id = admin_role_id
        self.ukry_role_id = ukry_role_id

    def is_admin(self, member: discord.Member) -> bool:
        return any(role.id == self.admin_role_id for role in member.roles)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="ukry_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(MSG_NOT_ADMIN, ephemeral=True)
            return

        member_id = int(interaction.channel.name.split("-")[-1])
        member = interaction.guild.get_member(member_id)

        if not member:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except discord.NotFound:
                member = None

        role = interaction.guild.get_role(self.ukry_role_id)

        if member and role:
            await member.add_roles(role)

        await interaction.response.send_message(MSG_APPROVED)
        await interaction.channel.delete()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="ukry_decline")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_admin(interaction.user):
            await interaction.response.send_message(MSG_NOT_ADMIN, ephemeral=True)
            return

        await interaction.response.send_message(MSG_DECLINED)
        await interaction.channel.delete()


# ── Reaction handlers ─────────────────────────────────────────────────────────

async def handle_reaction_add(
    bot,
    payload,
    role_map: dict,
    admin_role_id: int,
    ukry_role_id: int,
) -> None:
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            return

    emoji = str(payload.emoji)

    if emoji == "☢":
        admin_role = guild.get_role(admin_role_id)
        channel_name = f"ukry-verification-{member.id}"

        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        if existing_channel:
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        await channel.send(
            f"{member.mention} requested **Ukry clan membership**.",
            view=VerificationView(admin_role_id, ukry_role_id),
        )
        return

    if emoji in role_map:
        role = guild.get_role(role_map[emoji])
        if role:
            await member.add_roles(role)


async def handle_reaction_remove(bot, payload, role_map: dict) -> None:
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            return

    emoji = str(payload.emoji)

    if emoji in role_map and emoji != "☢":
        role = guild.get_role(role_map[emoji])
        if role:
            await member.remove_roles(role)
