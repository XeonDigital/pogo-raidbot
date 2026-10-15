from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from handlers.raid_handler import process_raid

INVALID_RAID = (False, "You gave an invalid **Weather Condition** of [`bogus`].\n", "5 Mewtwo Clear 5")


def sent_error_description(bot):
    return bot.send_ignore_error.await_args.kwargs["embed"].description


def assert_raid_was_not_listed(interaction):
    interaction.channel.send.assert_not_called()


def assert_raid_was_listed(interaction, followup_text):
    interaction.channel.send.assert_awaited_once()
    assert "Raid listed" in followup_text(interaction)


def post_raid(run, interaction, bot, pokemon="Mewtwo", weather="Clear", invite_slots="5", tier="5"):
    run(process_raid(interaction, bot, tier, pokemon, weather, invite_slots))


def valid_raid_message():
    def fake_validate(interaction, tier, pokemon_name, weather, invite_slots):
        return (True, SimpleNamespace(title=pokemon_name), "")

    return patch(
        "handlers.raid_handler.validate_and_format_message",
        side_effect=fake_validate,
    )


@pytest.fixture
def ready_to_list():
    with valid_raid_message(), \
            patch("handlers.raid_handler.REQH.check_if_request_message_exists", new_callable=AsyncMock, return_value=(None, None, None, None)), \
            patch("handlers.raid_handler.REQH.get_request_channel", new_callable=AsyncMock, return_value=None), \
            patch("handlers.raid_lobby_handler.get_raid_lobby_category_by_guild_id", new_callable=AsyncMock, return_value=None), \
            patch("handlers.raid_handler.SH.toggle_raid_sticky", new_callable=AsyncMock):
        yield


class TestRaidGuards:
    def test_wrong_channel_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context(raid_channel=False)
        post_raid(run, interaction, bot)

        assert "correct raid channel" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()

    def test_already_in_a_raid_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context()
        bot.database.fetchrow.return_value = {"message_id": 99, "user_id": interaction.user.id}
        post_raid(run, interaction, bot)

        assert "already in a raid" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()

    def test_leftover_lobby_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context()
        with patch(
            "handlers.raid_lobby_handler.get_lobby_data_by_user_id",
            new_callable=AsyncMock,
            return_value={"lobby_channel_id": 7, "raid_message_id": 99},
        ):
            post_raid(run, interaction, bot)

        assert "lobby open" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()

    def test_unverified_host_cannot_list_more_than_five(self, run, make_context):
        interaction, bot = make_context()
        post_raid(run, interaction, bot, invite_slots="10")

        assert "more than 5" in sent_error_description(bot)
        assert_raid_was_not_listed(interaction)
        interaction.followup.send.assert_not_called()

    def test_pokemon_not_in_rotation_is_rejected(self, run, make_context):
        interaction, bot = make_context()
        with valid_raid_message():
            post_raid(run, interaction, bot, pokemon="Dialga")

        assert "not currently in rotation" in sent_error_description(bot)
        assert "Dialga" in sent_error_description(bot)
        assert_raid_was_not_listed(interaction)

    def test_invalid_arguments_are_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context()
        with patch(
            "handlers.raid_handler.validate_and_format_message",
            return_value=INVALID_RAID,
        ):
            post_raid(run, interaction, bot, weather="bogus")

        message = followup_text(interaction)
        assert "invalid **Weather Condition**" in message
        # process_raid prefixes the validator's suggestion with /raid so the user can copy it
        assert "/raid 5 Mewtwo Clear 5" in message
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()


class TestRaidListing:
    def test_raid_is_listed_when_the_boss_is_in_rotation(self, run, make_context, ready_to_list, followup_text):
        interaction, bot = make_context()
        post_raid(run, interaction, bot)

        assert_raid_was_listed(interaction, followup_text)
        bot.database.execute.assert_awaited_once()
        bot.send_ignore_error.assert_not_called()

    def test_verified_host_can_list_more_than_five(self, run, make_context, ready_to_list, followup_text):
        interaction, bot = make_context(verified=True)
        post_raid(run, interaction, bot, invite_slots="10")

        assert_raid_was_listed(interaction, followup_text)
        bot.send_ignore_error.assert_not_called()
