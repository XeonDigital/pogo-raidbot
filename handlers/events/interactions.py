import discord

from handlers import raid_lobby_handler as RLH


def format_slash_command(interaction: discord.Interaction) -> str:
    data = interaction.data or {}
    names = [data.get("name") or "unknown"]
    option_parts = []

    def collect(options):
        for option in options or []:
            option_type = option.get("type")
            if option_type in (discord.AppCommandOptionType.subcommand.value,
                               discord.AppCommandOptionType.subcommand_group.value):
                names.append(option.get("name") or "unknown")
                collect(option.get("options"))
            else:
                option_parts.append(f"{option.get('name')}:{option.get('value')}")

    collect(data.get("options"))
    command = "/" + " ".join(names)
    if option_parts:
        command = f"{command} {' '.join(option_parts)}"
    return command


async def on_interaction_handle(interaction: discord.Interaction, bot):
    if interaction.type != discord.InteractionType.application_command:
        return
    if not interaction.guild:
        return
    if interaction.user and interaction.user.bot:
        return
    if not bot.categories_allowed:
        return

    # Prefer the invocation channel, but host commands like /extend work from anywhere.
    lobby_data = None
    channel_id = interaction.channel_id or (interaction.channel.id if interaction.channel else None)
    if channel_id:
        lobby_data = await RLH.get_lobby_data_by_lobby_id(bot, channel_id)
    if not lobby_data and interaction.user:
        lobby_data = await RLH.get_lobby_data_by_user_id(bot, interaction.user.id)
    if not lobby_data:
        return

    lobby_channel = await bot.retrieve_channel(int(lobby_data.get("lobby_channel_id")))
    if not lobby_channel:
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
