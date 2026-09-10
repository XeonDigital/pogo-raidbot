import discord

from handlers import raid_lobby_handler as RLH
from handlers.events.slash_logging import (
    format_slash_command,
    resolve_interaction_channel_id,
    should_defer_slash_command_log,
    should_log_slash_interaction,
)


async def log_slash_command_for_lobby(bot, interaction, lobby_channel, lobby_data):
    if not lobby_channel or not lobby_data:
        return
    await RLH.log_lobby_activity(
        bot,
        guild=interaction.guild,
        user=interaction.user,
        lobby_channel=lobby_channel,
        lobby_data=lobby_data,
        description=format_slash_command(interaction),
        jump_url=lobby_channel.jump_url,
    )


async def on_interaction_handle(interaction: discord.Interaction, bot):
    if not should_log_slash_interaction(interaction, bot):
        return
    if should_defer_slash_command_log(interaction):
        return

    # Prefer the invocation channel, but host commands like /extend work from anywhere.
    lobby_data = None
    channel_id = resolve_interaction_channel_id(interaction)
    if channel_id:
        lobby_data = await RLH.get_lobby_data_by_lobby_id(bot, channel_id)
    if not lobby_data and interaction.user:
        lobby_data = await RLH.get_lobby_data_by_user_id(bot, interaction.user.id)
    if not lobby_data:
        return

    lobby_channel = await bot.retrieve_channel(int(lobby_data.get("lobby_channel_id")))
    if not lobby_channel:
        return

    await log_slash_command_for_lobby(bot, interaction, lobby_channel, lobby_data)
