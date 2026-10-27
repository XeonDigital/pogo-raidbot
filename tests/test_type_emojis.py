from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.event_listeners import Listeners
from handlers.pokebattler import api_helper as AH
from handlers.pokebattler.api_helper import get_counter


def test_bind_type_emojis_uses_this_apps_psychic_icon():
    original = AH.TYPE_EMOJIS
    try:
        AH.bind_type_emojis(
            [
                {"name": "psychic", "id": "1"},
                {"name": "ico_15_dragon", "id": "2"},
            ]
        )
        assert AH.TYPE_EMOJIS["PSYCHIC"] == "<:psychic:1>"
        assert AH.TYPE_EMOJIS["DRAGON"] == "<:ico_15_dragon:2>"
    finally:
        AH.TYPE_EMOJIS = original


def test_bind_type_emojis_accepts_emoji_objects():
    original = AH.TYPE_EMOJIS
    try:
        AH.bind_type_emojis([SimpleNamespace(name="fire", id="9")])
        assert AH.TYPE_EMOJIS["FIRE"] == "<:fire:9>"
    finally:
        AH.TYPE_EMOJIS = original


def test_bind_type_emojis_keeps_hardcoded_ids_when_none_match():
    original = AH.TYPE_EMOJIS
    try:
        AH.bind_type_emojis([])
        assert AH.TYPE_EMOJIS["PSYCHIC"] == original["PSYCHIC"]
    finally:
        AH.TYPE_EMOJIS = original


def make_listeners(bot):
    cog = Listeners.__new__(Listeners)
    cog._Listeners__bot = bot
    cog._has_synced = True
    return cog


def test_on_ready_binds_application_emojis(run):
    bot = SimpleNamespace(
        user=SimpleNamespace(name="test-bot", id=1),
        application_id=1,
        guilds=[],
        http=SimpleNamespace(request=AsyncMock(return_value={"items": [{"name": "psychic", "id": "1"}]})),
    )
    with patch("cogs.event_listeners.AH.bind_type_emojis") as bind:
        run(make_listeners(bot).on_ready())
    bind.assert_called_once_with([{"name": "psychic", "id": "1"}])


def test_on_ready_still_starts_if_emoji_bind_fails(run):
    bot = SimpleNamespace(
        user=SimpleNamespace(name="test-bot", id=1),
        application_id=None,
        guilds=[],
        http=SimpleNamespace(request=AsyncMock(side_effect=RuntimeError("forbidden"))),
    )
    with patch("cogs.event_listeners.AH.bind_type_emojis") as bind, patch("builtins.print") as mock_print:
        run(make_listeners(bot).on_ready())
    bind.assert_not_called()
    assert "Failed to bind type emojis" in mock_print.call_args.args[0]


@contextmanager
def valid_counter_lookups(bot):
    embed = SimpleNamespace(set_thumbnail=Mock())
    bot.dex.get_counter_for = AsyncMock(return_value=embed)
    with patch("handlers.pokebattler.api_helper.validate_tier", return_value=(True, "5")), \
            patch("handlers.pokebattler.api_helper.validate_pokemon", return_value=(True, "Mewtwo", "", "go:pm150")), \
            patch("handlers.pokebattler.api_helper.validate_weather_argument", return_value=(True, "Clear", "")):
        yield embed


class TestGetCounter:
    def test_slash_command_sends_to_channel_and_notifies(self, run, make_bot, make_interaction):
        bot = make_bot()
        interaction = make_interaction()
        with valid_counter_lookups(bot) as embed:
            run(get_counter(bot, interaction, "5", "Mewtwo", "Clear"))
        interaction.channel.send.assert_awaited_once()
        assert interaction.channel.send.await_args.kwargs["embed"] is embed
        assert "Counters sent" in interaction.followup.send.await_args.args[0]

    def test_raid_auto_post_uses_lobby_and_skips_followup(self, run, make_bot, make_interaction, make_channel):
        bot = make_bot()
        interaction = make_interaction()
        lobby = make_channel(channel_id=200)
        with valid_counter_lookups(bot):
            run(get_counter(bot, interaction, "5", "Mewtwo", "Clear", lobby, False))
        lobby.send.assert_awaited_once()
        interaction.channel.send.assert_not_called()
        interaction.followup.send.assert_not_called()

    def test_send_errors_are_swallowed(self, run, make_bot, make_interaction):
        bot = make_bot()
        interaction = make_interaction()
        interaction.channel.send.side_effect = discord.DiscordException("missing permissions")
        with valid_counter_lookups(bot):
            run(get_counter(bot, interaction, "5", "Mewtwo", "Clear"))
        interaction.followup.send.assert_not_called()

    def test_missing_tier_is_rejected(self, run, make_bot, make_interaction):
        bot = make_bot()
        interaction = make_interaction()
        run(get_counter(bot, interaction, "", "Mewtwo", "Clear"))
        assert "No pokemon given" in interaction.followup.send.await_args.args[0]
        interaction.channel.send.assert_not_called()

    def test_mega_without_a_name_is_rejected(self, run, make_bot, make_interaction):
        bot = make_bot()
        interaction = make_interaction()
        run(get_counter(bot, interaction, "mega", "", "Clear"))
        assert "No pokemon given" in interaction.followup.send.await_args.args[0]
        interaction.channel.send.assert_not_called()

    def test_invalid_arguments_are_sent_together(self, run, make_bot, make_interaction):
        bot = make_bot()
        interaction = make_interaction()
        with patch("handlers.pokebattler.api_helper.validate_tier", return_value=(False, "bad tier\n")), \
                patch("handlers.pokebattler.api_helper.validate_pokemon", return_value=(False, "bad pokemon\n", "Mewtwo", None)), \
                patch("handlers.pokebattler.api_helper.validate_weather_argument", return_value=(False, "bad weather\n", "Clear")):
            run(get_counter(bot, interaction, "9", "Bogus", "bogus"))
        message = interaction.followup.send.await_args.args[0]
        assert "bad tier" in message
        assert "bad pokemon" in message
        assert "Did you mean **Clear**" in message
        interaction.channel.send.assert_not_called()
