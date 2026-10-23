from unittest.mock import patch

from handlers.request_handler import check_if_valid_request_channel, request_pokemon_handle

CHANNEL_ID = 100
INVALID_POKEMON = (False, "You gave an invalid **Pokemon Name** of [`mewtw`].\n", "Mewtwo", 0)
VALID_DIALGA = (True, "Dialga", "", "go:pm483")
VALID_MEWTWO = (True, "Mewtwo", "", "go:pm150")


def sent_error_description(bot):
    return bot.send_ignore_error.await_args.kwargs["embed"].description


def user_dms(interaction):
    return [call.args[0] for call in interaction.user.send.await_args_list if call.args]


def call_request(run, bot, interaction, tier=None, pokemon_name=None):
    run(request_pokemon_handle(bot, interaction, tier, pokemon_name))


class TestRequestChannel:
    def test_cached_channel_skips_the_database(self, run, bot):
        bot.request_channel_cache.add(CHANNEL_ID)
        assert run(check_if_valid_request_channel(bot, CHANNEL_ID)) is True
        bot.database.fetchrow.assert_not_called()

    def test_registered_channel_is_cached(self, run, bot):
        bot.database.fetchrow.return_value = {"channel_id": CHANNEL_ID}
        assert run(check_if_valid_request_channel(bot, CHANNEL_ID)) is True
        assert CHANNEL_ID in bot.request_channel_cache

    def test_unknown_channel_is_rejected(self, run, bot):
        assert run(check_if_valid_request_channel(bot, CHANNEL_ID)) is False
        assert CHANNEL_ID not in bot.request_channel_cache


class TestRequestGuards:
    def test_missing_tier_is_rejected(self, run, bot, interaction):
        call_request(run, bot, interaction)

        assert "No pokemon given to request" in user_dms(interaction)[0]
        bot.send_ignore_error.assert_not_called()

    def test_mega_without_a_name_is_rejected(self, run, bot, interaction):
        call_request(run, bot, interaction, tier="mega")

        assert "No pokemon given to request" in user_dms(interaction)[0]
        bot.send_ignore_error.assert_not_called()

    def test_name_is_taken_from_tier_when_pokemon_name_is_missing(self, run, bot, interaction):
        with patch("handlers.request_handler.validate_pokemon", return_value=INVALID_POKEMON) as validate:
            call_request(run, bot, interaction, tier="Mewtwo")
        validate.assert_called_once_with("Mewtwo", "")
        assert all("No pokemon given to request" not in dm for dm in user_dms(interaction))

    def test_invalid_name_sends_a_retry_command(self, run, bot, interaction):
        with patch("handlers.request_handler.validate_pokemon", return_value=INVALID_POKEMON):
            call_request(run, bot, interaction, tier="mewtw")

        dms = user_dms(interaction)
        assert "invalid **Pokemon Name**" in dms[0]
        # request_pokemon_handle prefixes the validator's suggestion with /request so the user can copy it
        assert dms[1] == "/request Mewtwo"
        bot.send_ignore_error.assert_not_called()


class TestRequestRotation:
    def test_pokemon_not_in_rotation_is_rejected(self, run, bot, interaction):
        with patch("handlers.request_handler.validate_pokemon", return_value=VALID_DIALGA), \
                patch("handlers.request_handler.set_up_request_role_and_message") as setup:
            call_request(run, bot, interaction, tier="Dialga")

        assert "not currently in rotation" in sent_error_description(bot)
        assert "Dialga" in sent_error_description(bot)
        setup.assert_not_called()
        interaction.user.send.assert_not_called()
