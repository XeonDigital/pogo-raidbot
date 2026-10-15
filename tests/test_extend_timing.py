from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from handlers.raid_lobby_management import extend_duration_of_lobby

POSTED_AT = datetime(2026, 10, 12, 17, 0, tzinfo=timezone.utc)


def lobby_row(total_minutes, raid_message_id=99, lobby_channel_id=7):
    return {
        "posted_at": POSTED_AT,
        "delete_at": POSTED_AT + timedelta(minutes=total_minutes),
        "raid_message_id": raid_message_id,
        "lobby_channel_id": lobby_channel_id,
    }


@pytest.fixture
def run_extend(run, make_bot, make_channel, make_user):
    def factory(lobby_data, minutes=None, missing_channel=False):
        channel = None if missing_channel else make_channel()
        bot = make_bot()
        bot.retrieve_channel.return_value = channel
        user = make_user()
        with patch("handlers.raid_lobby_management.RLH.get_lobby_data_by_user_id", new_callable=AsyncMock) as get_lobby, \
                patch("handlers.raid_lobby_management.RLH.update_delete_time_with_given_time", new_callable=AsyncMock) as update, \
                patch("handlers.raid_lobby_management.RLH.remove_lobby_by_lobby_id", new_callable=AsyncMock) as remove:
            get_lobby.return_value = lobby_data
            run(extend_duration_of_lobby(bot, user, minutes=minutes))
        return user, channel, update, remove

    return factory


def test_extend_noops_when_user_is_not_hosting(run_extend):
    user, channel, update, remove = run_extend(None, minutes=10)
    update.assert_not_called()
    remove.assert_not_called()
    user.send.assert_not_called()
    channel.send.assert_not_called()


def test_extend_cleans_up_when_lobby_channel_is_gone(run_extend):
    lobby_data = lobby_row(15)
    user, channel, update, remove = run_extend(lobby_data, minutes=10, missing_channel=True)
    update.assert_not_called()
    remove.assert_awaited_once()
    user.send.assert_not_called()


def test_extend_adds_requested_minutes_to_delete_at(run_extend):
    lobby_data = lobby_row(15)
    user, channel, update, remove = run_extend(lobby_data, minutes=10)
    expected = lobby_data["delete_at"] + timedelta(minutes=10)
    update.assert_awaited_once()
    assert update.await_args.args[1] == expected
    assert update.await_args.args[2] == 99
    remove.assert_not_called()
    user.send.assert_not_called()
    channel.send.assert_awaited_once()
    assert "10 minutes" in channel.send.await_args.kwargs["embed"].description


def test_extend_defaults_to_ten_minutes_on_the_clock(run_extend):
    lobby_data = lobby_row(15)
    user, channel, update, remove = run_extend(lobby_data, minutes=None)
    expected = lobby_data["delete_at"] + timedelta(minutes=10)
    assert update.await_args.args[1] == expected
    assert "10 minutes" in channel.send.await_args.kwargs["embed"].description


def test_extend_caps_at_forty_five_minute_total(run_extend):
    lobby_data = lobby_row(40)
    user, channel, update, remove = run_extend(lobby_data, minutes=10)
    expected = POSTED_AT + timedelta(minutes=45)
    assert update.await_args.args[1] == expected
    assert "5 minutes" in channel.send.await_args.kwargs["embed"].description
    user.send.assert_not_called()


def test_extend_refuses_when_already_at_the_cap(run_extend):
    lobby_data = lobby_row(45)
    user, channel, update, remove = run_extend(lobby_data, minutes=10)
    update.assert_not_called()
    channel.send.assert_not_called()
    user.send.assert_awaited_once()
    assert "45 minutes" in user.send.await_args.kwargs["embed"].description
