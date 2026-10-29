from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from handlers.raid_handler import RaidTierPickView, process_raid

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
        return (True, SimpleNamespace(title=pokemon_name, set_footer=Mock()), "")

    return patch(
        "handlers.raid_handler.validate_and_format_message",
        side_effect=fake_validate,
    )


@pytest.fixture
def mock_get_counter():
    with patch("handlers.raid_handler.get_counter", new_callable=AsyncMock) as mocked:
        yield mocked


@pytest.fixture
def ready_to_list(mock_get_counter):
    with valid_raid_message(), \
            patch("handlers.raid_handler.REQH.check_if_request_message_exists", new_callable=AsyncMock, return_value=(None, None, None, None)), \
            patch("handlers.raid_handler.REQH.get_request_channel", new_callable=AsyncMock, return_value=None), \
            patch("handlers.raid_lobby_handler.get_raid_lobby_category_by_guild_id", new_callable=AsyncMock, return_value=None), \
            patch("handlers.raid_handler.SH.toggle_raid_sticky", new_callable=AsyncMock):
        yield


class TestRaidGuards:
    @pytest.fixture(autouse=True)
    def _patch_counters(self, mock_get_counter):
        self.get_counter = mock_get_counter

    def test_wrong_channel_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context(raid_channel=False)
        post_raid(run, interaction, bot)

        assert "correct raid channel" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()
        self.get_counter.assert_not_called()

    def test_already_in_a_raid_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context()
        bot.database.fetchrow.return_value = {"message_id": 99, "user_id": interaction.user.id}
        post_raid(run, interaction, bot)

        assert "already in a raid" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)
        bot.send_ignore_error.assert_not_called()
        self.get_counter.assert_not_called()

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
        self.get_counter.assert_not_called()

    def test_unverified_host_cannot_list_more_than_five(self, run, make_context):
        interaction, bot = make_context()
        post_raid(run, interaction, bot, invite_slots="10")

        assert "more than 5" in sent_error_description(bot)
        assert_raid_was_not_listed(interaction)
        interaction.followup.send.assert_not_called()
        self.get_counter.assert_not_called()

    def test_pokemon_not_in_rotation_is_rejected(self, run, make_context):
        interaction, bot = make_context()
        with valid_raid_message():
            post_raid(run, interaction, bot, pokemon="Dialga")

        assert "not currently in rotation" in sent_error_description(bot)
        assert "Dialga" in sent_error_description(bot)
        assert_raid_was_not_listed(interaction)
        self.get_counter.assert_not_called()

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
        self.get_counter.assert_not_called()


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

    def test_counters_are_posted_to_the_listing_channel_without_a_lobby(self, run, make_context, ready_to_list, mock_get_counter, followup_text):
        interaction, bot = make_context()
        post_raid(run, interaction, bot)

        assert_raid_was_listed(interaction, followup_text)
        mock_get_counter.assert_awaited_once_with(bot, interaction, "5", "Mewtwo", "Clear", interaction.channel, False)

    def test_counters_are_posted_to_the_lobby_when_one_exists(self, run, make_context, mock_get_counter, followup_text, make_channel):
        interaction, bot = make_context()
        lobby = make_channel(channel_id=200)
        lobby.mention = "<#200>"
        with valid_raid_message(), \
                patch("handlers.raid_handler.REQH.check_if_request_message_exists", new_callable=AsyncMock, return_value=(None, None, None, None)), \
                patch("handlers.raid_handler.REQH.get_request_channel", new_callable=AsyncMock, return_value=None), \
                patch("handlers.raid_lobby_handler.get_raid_lobby_category_by_guild_id", new_callable=AsyncMock, return_value={"category_id": 1}), \
                patch("handlers.raid_lobby_handler.create_raid_lobby", new_callable=AsyncMock, return_value=lobby), \
                patch("handlers.raid_handler.SH.toggle_raid_sticky", new_callable=AsyncMock):
            post_raid(run, interaction, bot)

        assert_raid_was_listed(interaction, followup_text)
        mock_get_counter.assert_awaited_once_with(bot, interaction, "5", "Mewtwo", "Clear", lobby, False)

    def test_raid_is_still_listed_when_counters_fail(self, run, make_context, ready_to_list, mock_get_counter, followup_text):
        mock_get_counter.side_effect = RuntimeError("pokebattler down")
        interaction, bot = make_context()
        post_raid(run, interaction, bot)

        assert_raid_was_listed(interaction, followup_text)


class TestRaidBossInference:
    def test_missing_tier_is_inferred_when_only_one_rotation_match(self, run, make_context, ready_to_list, mock_get_counter, followup_text):
        interaction, bot = make_context()
        post_raid(run, interaction, bot, weather="unknown", tier=None)

        assert_raid_was_listed(interaction, followup_text)
        mock_get_counter.assert_awaited_once_with(bot, interaction, "5", "Mewtwo", "unknown", interaction.channel, False)

    def test_ambiguous_boss_prompts_for_tier(self, run, make_context, followup_text):
        interaction, bot = make_context()
        bot.dex.matching_rotation_bosses = Mock(return_value=[
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=True),
        ])
        post_raid(run, interaction, bot, tier=None)

        message = followup_text(interaction)
        assert "more than one raid tier" in message
        view = interaction.followup.send.await_args.kwargs["view"]
        labels = [item.label for item in view.children]
        assert "5" in labels
        assert "5 Shadow" in labels
        assert_raid_was_not_listed(interaction)

    def test_provided_tier_disambiguates_when_slash_tiers_differ(self, run, make_context, ready_to_list, mock_get_counter, followup_text):
        interaction, bot = make_context()
        bot.dex.is_current_raid_boss = Mock(return_value=True)
        bot.dex.matching_rotation_bosses = Mock(return_value=[
            SimpleNamespace(name="Gengar", slash_tier="3", shadow=False),
            SimpleNamespace(name="Gengar", slash_tier="mega", shadow=False),
        ])
        post_raid(run, interaction, bot, pokemon="Gengar", tier="mega")

        assert_raid_was_listed(interaction, followup_text)
        mock_get_counter.assert_awaited_once_with(bot, interaction, "mega", "Gengar", "Clear", interaction.channel, False)

    def test_already_resolved_skips_the_tier_prompt(self, run, make_context, ready_to_list, followup_text):
        interaction, bot = make_context()
        bot.dex.matching_rotation_bosses = Mock(return_value=[
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=True),
        ])
        run(process_raid(interaction, bot, "5", "Shadow Mewtwo", "Clear", "5", True))

        assert_raid_was_listed(interaction, followup_text)
        bot.dex.matching_rotation_bosses.assert_not_called()

    def test_shadow_button_continues_with_that_form(self, run):
        matches = [
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=True),
        ]
        view = RaidTierPickView(None, "Mewtwo", "unknown", "5", matches, owner_id=5)
        button = next(item for item in view.children if item.match.shadow)
        interaction = SimpleNamespace(
            user=SimpleNamespace(id=5),
            response=SimpleNamespace(
                edit_message=AsyncMock(),
                is_done=Mock(return_value=True),
                defer=AsyncMock(),
            ),
        )
        with patch("handlers.raid_handler.process_raid", new_callable=AsyncMock) as mocked:
            run(button.callback(interaction))

        mocked.assert_awaited_once_with(interaction, None, "5", "Shadow Mewtwo", "unknown", "5", True)

    def test_mega_button_is_labeled_mega(self):
        view = RaidTierPickView(
            None, "Gengar", "unknown", "5",
            [SimpleNamespace(name="Gengar", slash_tier="mega", shadow=False)],
            owner_id=5,
        )
        assert view.children[0].label == "Mega"

    def test_same_slash_tier_still_prompts_when_shadow_and_regular_both_match(self, run, make_context, followup_text):
        interaction, bot = make_context()
        bot.dex.matching_rotation_bosses = Mock(return_value=[
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=True),
        ])
        post_raid(run, interaction, bot, tier="5")

        assert "more than one raid tier" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)

    def test_blank_weather_defaults_to_unknown(self, run, make_context, ready_to_list, mock_get_counter, followup_text):
        interaction, bot = make_context()
        post_raid(run, interaction, bot, weather="", tier=None)

        assert_raid_was_listed(interaction, followup_text)
        mock_get_counter.assert_awaited_once_with(bot, interaction, "5", "Mewtwo", "unknown", interaction.channel, False)

    def test_unknown_pokemon_without_tier_is_rejected(self, run, make_context, followup_text):
        interaction, bot = make_context()
        post_raid(run, interaction, bot, pokemon="missingno", tier=None)

        assert "invalid **Pokemon Name**" in followup_text(interaction)
        assert_raid_was_not_listed(interaction)

    def test_known_pokemon_not_in_rotation_without_tier_is_rejected(self, run, make_context):
        interaction, bot = make_context()
        with patch("handlers.raid_handler.validate_pokemon", return_value=(True, "Dialga", "", "go:pm483")):
            post_raid(run, interaction, bot, pokemon="Dialga", tier=None)

        assert "not currently in rotation" in sent_error_description(bot)
        assert "Dialga" in sent_error_description(bot)
        assert_raid_was_not_listed(interaction)

    def test_tier_prompt_rejects_other_users(self, run):
        view = RaidTierPickView(None, "Mewtwo", "unknown", "5", [
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
        ], owner_id=5)
        other = SimpleNamespace(
            user=SimpleNamespace(id=99),
            response=SimpleNamespace(send_message=AsyncMock()),
        )

        assert run(view.interaction_check(other)) is False
        other.response.send_message.assert_awaited_once()

    def test_tier_prompt_disables_buttons_on_timeout(self, run):
        view = RaidTierPickView(None, "Mewtwo", "unknown", "5", [
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
        ], owner_id=5)
        view.message = SimpleNamespace(edit=AsyncMock())

        run(view.on_timeout())

        assert view.children[0].disabled is True
        view.message.edit.assert_awaited_once_with(view=view)

    def test_tier_prompt_timeout_swallows_edit_errors(self, run):
        view = RaidTierPickView(None, "Mewtwo", "unknown", "5", [
            SimpleNamespace(name="Mewtwo", slash_tier="5", shadow=False),
        ], owner_id=5)
        view.message = SimpleNamespace(edit=AsyncMock(side_effect=discord.DiscordException("gone")))

        run(view.on_timeout())

        assert view.children[0].disabled is True
