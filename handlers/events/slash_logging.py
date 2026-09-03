import discord


def format_slash_command(interaction) -> str:
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


def resolve_interaction_channel_id(interaction):
    if interaction.channel_id:
        return interaction.channel_id
    if interaction.channel:
        return interaction.channel.id
    return None


def should_log_slash_interaction(interaction, bot) -> bool:
    if interaction.type != discord.InteractionType.application_command:
        return False
    if not interaction.guild:
        return False
    if interaction.user and interaction.user.bot:
        return False
    if not bot.categories_allowed:
        return False
    return True


def should_skip_message_logging(message) -> bool:
    if message.author.bot:
        return True
    return message.type == discord.MessageType.chat_input_command


def slash_command_name(interaction) -> str:
    data = interaction.data or {}
    return data.get("name") or ""


# /raid creates the lobby during the command, so invoke-time logging would
# miss it or race and double-log. It is logged after a successful create.
DEFERRED_SLASH_LOG_COMMANDS = frozenset({"raid"})


def should_defer_slash_command_log(interaction) -> bool:
    return slash_command_name(interaction) in DEFERRED_SLASH_LOG_COMMANDS


def resolve_extension_minutes(minutes=None) -> int:
    return 10 if minutes is None else int(minutes)
