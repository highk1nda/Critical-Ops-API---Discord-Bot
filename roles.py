import discord

REACTION_MESSAGE_ID = 1477285069432422483


class VerificationView(discord.ui.View):

    def __init__(self, admin_role_id, ukry_role_id):
        super().__init__(timeout=None)

        self.admin_role_id = admin_role_id
        self.ukry_role_id = ukry_role_id

    def is_admin(self, member):
        return any(role.id == self.admin_role_id for role in member.roles)

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.green,
        custom_id="ukry_approve"
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not self.is_admin(interaction.user):
            await interaction.response.send_message("You are not admin.", ephemeral=True)
            return

        member_id = int(interaction.channel.name.split("-")[-1])
        member = interaction.guild.get_member(member_id)

        # Fallback to API fetch if not in cache
        if not member:
            try:
                member = await interaction.guild.fetch_member(member_id)
            except discord.NotFound:
                member = None

        role = interaction.guild.get_role(self.ukry_role_id)

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

        if not self.is_admin(interaction.user):
            await interaction.response.send_message("You are not admin.", ephemeral=True)
            return

        await interaction.response.send_message("Declined.")
        await interaction.channel.delete()


# Reaction Event


async def handle_reaction_add(bot, payload, role_map, admin_role_id, ukry_role_id):
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    # Use cache first, fall back to API fetch
    member = guild.get_member(payload.user_id)
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            return

    emoji = str(payload.emoji)

    # Verification request
    if emoji == "☢":

        admin_role = guild.get_role(admin_role_id)

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
            view=VerificationView(admin_role_id, ukry_role_id)
        )

        return

    # Normal reaction roles
    if emoji in role_map:
        role = guild.get_role(role_map[emoji])
        if role:
            await member.add_roles(role)


async def handle_reaction_remove(bot, payload, role_map):
    if payload.message_id != REACTION_MESSAGE_ID:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    # Use cache first, fall back to API fetch
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