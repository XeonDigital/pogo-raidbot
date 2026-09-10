from types import SimpleNamespace

import discord

from handlers.events.slash_logging import (
    format_slash_command,
    resolve_extension_minutes,
    resolve_interaction_channel_id,
    should_defer_slash_command_log,
    should_log_slash_interaction,
    should_skip_message_logging,
)


def test_format_naked_extend():
    interaction = SimpleNamespace(data={"name": "extend", "options": []})
    assert format_slash_command(interaction) == "/extend"


def test_format_extend_with_minutes():
    interaction = SimpleNamespace(data={
        "name": "extend",
        "options": [{"name": "minutes", "type": 4, "value": 5}],
    })
    assert format_slash_command(interaction) == "/extend minutes:5"


def test_format_missing_data_is_unknown():
    assert format_slash_command(SimpleNamespace(data=None)) == "/unknown"
    assert format_slash_command(SimpleNamespace(data={})) == "/unknown"


def test_format_subcommand_and_options():
    interaction = SimpleNamespace(data={
        "name": "raid",
        "options": [{
            "name": "post",
            "type": discord.AppCommandOptionType.subcommand.value,
            "options": [
                {"name": "tier", "type": 3, "value": "5"},
                {"name": "pokemon", "type": 3, "value": "Mewtwo"},
            ],
        }],
    })
    assert format_slash_command(interaction) == "/raid post tier:5 pokemon:Mewtwo"


def test_resolve_channel_id_prefers_channel_id():
    interaction = SimpleNamespace(
        channel_id=111,
        channel=SimpleNamespace(id=222),
    )
    assert resolve_interaction_channel_id(interaction) == 111


def test_resolve_channel_id_falls_back_to_channel():
    interaction = SimpleNamespace(channel_id=None, channel=SimpleNamespace(id=222))
    assert resolve_interaction_channel_id(interaction) == 222


def test_resolve_channel_id_when_missing():
    interaction = SimpleNamespace(channel_id=None, channel=None)
    assert resolve_interaction_channel_id(interaction) is None


def _interaction(**overrides):
    defaults = dict(
        type=discord.InteractionType.application_command,
        guild=SimpleNamespace(id=1),
        user=SimpleNamespace(bot=False),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_should_log_application_command_in_guild():
    bot = SimpleNamespace(categories_allowed=True)
    assert should_log_slash_interaction(_interaction(), bot) is True


def test_should_not_log_non_command_interactions():
    bot = SimpleNamespace(categories_allowed=True)
    interaction = _interaction(type=discord.InteractionType.autocomplete)
    assert should_log_slash_interaction(interaction, bot) is False


def test_should_not_log_without_guild():
    bot = SimpleNamespace(categories_allowed=True)
    assert should_log_slash_interaction(_interaction(guild=None), bot) is False


def test_should_not_log_bot_users():
    bot = SimpleNamespace(categories_allowed=True)
    interaction = _interaction(user=SimpleNamespace(bot=True))
    assert should_log_slash_interaction(interaction, bot) is False


def test_should_not_log_when_categories_disabled():
    bot = SimpleNamespace(categories_allowed=False)
    assert should_log_slash_interaction(_interaction(), bot) is False


def test_skip_bot_messages_and_slash_system_messages():
    bot_message = SimpleNamespace(
        author=SimpleNamespace(bot=True),
        type=discord.MessageType.default,
    )
    slash_message = SimpleNamespace(
        author=SimpleNamespace(bot=False),
        type=discord.MessageType.chat_input_command,
    )
    chat_message = SimpleNamespace(
        author=SimpleNamespace(bot=False),
        type=discord.MessageType.default,
    )
    assert should_skip_message_logging(bot_message) is True
    assert should_skip_message_logging(slash_message) is True
    assert should_skip_message_logging(chat_message) is False


def test_extend_defaults_to_ten_minutes():
    assert resolve_extension_minutes(None) == 10
    assert resolve_extension_minutes(5) == 5
    assert resolve_extension_minutes("5") == 5


def test_format_raid_command_with_options():
    interaction = SimpleNamespace(data={
        "name": "raid",
        "options": [
            {"name": "tier", "type": 3, "value": "5"},
            {"name": "pokemon_name", "type": 3, "value": "Mewtwo"},
            {"name": "weather", "type": 3, "value": "Clear"},
            {"name": "invite_slots", "type": 4, "value": 5},
        ],
    })
    assert format_slash_command(interaction) == "/raid tier:5 pokemon_name:Mewtwo weather:Clear invite_slots:5"


def test_raid_slash_log_is_deferred_until_success():
    raid = SimpleNamespace(data={"name": "raid"})
    extend = SimpleNamespace(data={"name": "extend"})
    empty = SimpleNamespace(data=None)
    assert should_defer_slash_command_log(raid) is True
    assert should_defer_slash_command_log(extend) is False
    assert should_defer_slash_command_log(empty) is False
