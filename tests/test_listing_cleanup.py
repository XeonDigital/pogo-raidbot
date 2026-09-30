import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from handlers.events import deletions
from handlers.raid_handler import remove_listing_for_raid
from handlers.raid_lobby_handler import delete_lobby, remove_listing_for_lobby
from handlers.raid_lobby_management import host_manual_remove_lobby
from handlers.startup_handler import start_lobby_removal_loop


def run(coro):
    return asyncio.run(coro)


def test_remove_listing_for_raid_noops_without_id():
    bot = SimpleNamespace(http=SimpleNamespace(delete_message=AsyncMock()))
    run(remove_listing_for_raid(bot, None))
    bot.http.delete_message.assert_not_called()


def test_remove_listing_for_raid_noops_when_row_missing():
    bot = SimpleNamespace(http=SimpleNamespace(delete_message=AsyncMock()))
    with patch("handlers.raid_handler.retrieve_raid_data_by_message_id", new_callable=AsyncMock) as retrieve, \
            patch("handlers.raid_handler.remove_raid_from_table", new_callable=AsyncMock) as remove_row:
        retrieve.return_value = None
        run(remove_listing_for_raid(bot, 123))
    remove_row.assert_not_called()
    bot.http.delete_message.assert_not_called()


def test_remove_listing_for_raid_deletes_row_before_message():
    bot = SimpleNamespace(http=SimpleNamespace(delete_message=AsyncMock()))
    raid_data = {"message_id": 11, "channel_id": 22, "guild_id": 33}
    order = []

    async def fake_remove(_bot, message_id):
        order.append(("table", message_id))

    async def fake_delete(channel_id, message_id):
        order.append(("message", channel_id, message_id))

    async def fake_sticky(_bot, _interaction, channel_id, guild_id):
        order.append(("sticky", channel_id, guild_id))

    bot.http.delete_message = AsyncMock(side_effect=fake_delete)
    with patch("handlers.raid_handler.retrieve_raid_data_by_message_id", new_callable=AsyncMock) as retrieve, \
            patch("handlers.raid_handler.remove_raid_from_table", side_effect=fake_remove), \
            patch("handlers.raid_handler.SH.toggle_raid_sticky", side_effect=fake_sticky):
        retrieve.return_value = raid_data
        run(remove_listing_for_raid(bot, 11))

    assert order == [
        ("table", 11),
        ("message", 22, 11),
        ("sticky", 22, 33),
    ]


def test_remove_listing_for_raid_still_toggles_sticky_if_message_gone():
    bot = SimpleNamespace(http=SimpleNamespace(delete_message=AsyncMock(side_effect=discord.DiscordException("unknown message"))))
    raid_data = {"message_id": 11, "channel_id": 22, "guild_id": 33}
    with patch("handlers.raid_handler.retrieve_raid_data_by_message_id", new_callable=AsyncMock) as retrieve, \
            patch("handlers.raid_handler.remove_raid_from_table", new_callable=AsyncMock) as remove_row, \
            patch("handlers.raid_handler.SH.toggle_raid_sticky", new_callable=AsyncMock) as sticky, \
            patch("builtins.print") as mock_print:
        retrieve.return_value = raid_data
        run(remove_listing_for_raid(bot, 11))
    remove_row.assert_awaited_once()
    sticky.assert_awaited_once()
    mock_print.assert_called_once()
    assert "Failed to delete raid listing message" in mock_print.call_args.args[0]


def test_remove_listing_for_raid_logs_sticky_errors():
    bot = SimpleNamespace(http=SimpleNamespace(delete_message=AsyncMock()))
    raid_data = {"message_id": 11, "channel_id": 22, "guild_id": 33}
    with patch("handlers.raid_handler.retrieve_raid_data_by_message_id", new_callable=AsyncMock) as retrieve, \
            patch("handlers.raid_handler.remove_raid_from_table", new_callable=AsyncMock), \
            patch("handlers.raid_handler.SH.toggle_raid_sticky", new_callable=AsyncMock, side_effect=discord.DiscordException("missing permissions")), \
            patch("builtins.print") as mock_print:
        retrieve.return_value = raid_data
        run(remove_listing_for_raid(bot, 11))
    bot.http.delete_message.assert_awaited_once()
    mock_print.assert_called_once()
    assert "toggle of raid sticky" in mock_print.call_args.args[0]


def test_remove_listing_for_lobby_noops_without_data():
    with patch("handlers.raid_lobby_handler.RH.remove_listing_for_raid", new_callable=AsyncMock) as remove_listing:
        run(remove_listing_for_lobby(SimpleNamespace(), None))
    remove_listing.assert_not_called()


def test_remove_listing_for_lobby_uses_raid_message_id():
    bot = SimpleNamespace()
    lobby_data = {"raid_message_id": 99}
    with patch("handlers.raid_lobby_handler.RH.remove_listing_for_raid", new_callable=AsyncMock) as remove_listing:
        run(remove_listing_for_lobby(bot, lobby_data))
    remove_listing.assert_awaited_once_with(bot, 99)


def test_delete_lobby_removes_listing_then_channel():
    bot = SimpleNamespace(
        remove_role_ignore_error=AsyncMock(),
        delete_ignore_error=AsyncMock(),
    )
    lobby = SimpleNamespace(
        id=7,
        members=[],
        guild=SimpleNamespace(roles=[]),
        send=AsyncMock(),
    )
    lobby_data = {"raid_message_id": 99}
    with patch("handlers.raid_lobby_handler.get_lobby_data_by_lobby_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.raid_lobby_handler.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing:
        get_lobby.return_value = lobby_data
        run(delete_lobby(bot, lobby))
    remove_listing.assert_awaited_once_with(bot, lobby_data)
    bot.delete_ignore_error.assert_awaited_once_with(lobby)


def test_guild_channel_delete_cleans_listing_for_lobby():
    bot = SimpleNamespace()
    channel = SimpleNamespace(id=7)
    lobby_data = {"raid_message_id": 99, "lobby_channel_id": 7}
    with patch("handlers.events.deletions.RLH.get_lobby_data_by_lobby_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.events.deletions.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing, \
            patch("handlers.events.deletions.RLH.remove_lobby_by_lobby_id", new_callable=AsyncMock) as remove_lobby, \
            patch("handlers.events.deletions.RLH.check_if_log_channel_and_purge_data", new_callable=AsyncMock) as purge:
        get_lobby.return_value = lobby_data
        run(deletions.on_guild_channel_delete(channel, bot))
    remove_listing.assert_awaited_once_with(bot, lobby_data)
    remove_lobby.assert_awaited_once_with(bot, lobby_data)
    purge.assert_not_called()


def test_guild_channel_delete_ignores_non_lobby_channels():
    bot = SimpleNamespace()
    channel = SimpleNamespace(id=8)
    with patch("handlers.events.deletions.RLH.get_lobby_data_by_lobby_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.events.deletions.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing, \
            patch("handlers.events.deletions.RLH.check_if_log_channel_and_purge_data", new_callable=AsyncMock) as purge:
        get_lobby.return_value = None
        run(deletions.on_guild_channel_delete(channel, bot))
    remove_listing.assert_not_called()
    purge.assert_awaited_once_with(bot, 8)


def test_host_close_deletes_lobby_when_channel_exists():
    bot = SimpleNamespace(retrieve_channel=AsyncMock())
    user = SimpleNamespace(id=5)
    lobby = SimpleNamespace(id=7)
    lobby_data = {"lobby_channel_id": 7, "raid_message_id": 99}
    bot.retrieve_channel.return_value = lobby
    with patch("handlers.raid_lobby_management.RLH.get_lobby_data_by_user_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.raid_lobby_management.RLH.delete_lobby", new_callable=AsyncMock) as delete, \
            patch("handlers.raid_lobby_management.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing:
        get_lobby.return_value = lobby_data
        run(host_manual_remove_lobby(bot, user))
    delete.assert_awaited_once_with(bot, lobby)
    remove_listing.assert_not_called()


def test_host_close_noops_when_user_is_not_hosting():
    bot = SimpleNamespace()
    user = SimpleNamespace(id=5, send=AsyncMock())
    with patch("handlers.raid_lobby_management.RLH.get_lobby_data_by_user_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.raid_lobby_management.RLH.delete_lobby", new_callable=AsyncMock) as delete, \
            patch("handlers.raid_lobby_management.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing:
        get_lobby.return_value = None
        run(host_manual_remove_lobby(bot, user))
    delete.assert_not_called()
    remove_listing.assert_not_called()
    user.send.assert_awaited_once()


def test_expiry_loop_removes_listing_if_lobby_channel_gone():
    async def scenario():
        bot = SimpleNamespace(
            database=True,
            retrieve_channel=AsyncMock(return_value=None),
            lobby_remove_trigger=asyncio.Event(),
        )
        lobby_data = {
            "lobby_channel_id": 7,
            "raid_message_id": 99,
            "delete_at": datetime.now(tz=timezone.utc) - timedelta(seconds=5),
        }
        listing_removed = asyncio.Event()

        async def mark_removed(_bot, data):
            assert data is lobby_data
            listing_removed.set()

        with patch("handlers.startup_handler.RLH.get_next_lobby_to_remove", new_callable=AsyncMock) as get_next, \
                patch("handlers.startup_handler.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing, \
                patch("handlers.startup_handler.RLH.remove_lobby_by_lobby_id", new_callable=AsyncMock) as remove_lobby, \
                patch("handlers.startup_handler.RLH.delete_lobby", new_callable=AsyncMock) as delete:
            get_next.side_effect = [lobby_data, None]
            remove_listing.side_effect = mark_removed
            task = asyncio.create_task(start_lobby_removal_loop(bot))
            try:
                await asyncio.wait_for(listing_removed.wait(), timeout=2)
                await asyncio.sleep(0)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            remove_listing.assert_awaited_once_with(bot, lobby_data)
            remove_lobby.assert_awaited_once_with(bot, lobby_data)
            delete.assert_not_called()

    run(scenario())


def test_host_close_still_removes_listing_if_lobby_channel_missing():
    bot = SimpleNamespace(retrieve_channel=AsyncMock(return_value=None))
    user = SimpleNamespace(id=5)
    lobby_data = {"lobby_channel_id": 7, "raid_message_id": 99}
    with patch("handlers.raid_lobby_management.RLH.get_lobby_data_by_user_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.raid_lobby_management.RLH.delete_lobby", new_callable=AsyncMock) as delete, \
            patch("handlers.raid_lobby_management.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing, \
            patch("handlers.raid_lobby_management.RLH.remove_lobby_by_lobby_id", new_callable=AsyncMock) as remove_lobby:
        get_lobby.return_value = lobby_data
        run(host_manual_remove_lobby(bot, user))
    delete.assert_not_called()
    remove_listing.assert_awaited_once_with(bot, lobby_data)
    remove_lobby.assert_awaited_once_with(bot, lobby_data)
