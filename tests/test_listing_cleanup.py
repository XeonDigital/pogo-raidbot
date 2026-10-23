import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from handlers.events import deletions
from handlers.events.reactions import handle_reaction_remove_raid, raw_reaction_add_handle
from handlers.raid_handler import remove_listing_for_raid
from handlers.raid_lobby_handler import delete_lobby, remove_listing_for_lobby
from handlers.raid_lobby_management import host_manual_remove_lobby
from handlers.startup_handler import start_lobby_removal_loop


def test_remove_listing_for_raid_noops_without_id(run, bot):
    run(remove_listing_for_raid(bot, None))
    bot.http.delete_message.assert_not_called()


def test_remove_listing_for_raid_noops_when_row_missing(run, bot):
    with patch("handlers.raid_handler.retrieve_raid_data_by_message_id", new_callable=AsyncMock) as retrieve, \
            patch("handlers.raid_handler.remove_raid_from_table", new_callable=AsyncMock) as remove_row:
        retrieve.return_value = None
        run(remove_listing_for_raid(bot, 123))
    remove_row.assert_not_called()
    bot.http.delete_message.assert_not_called()


def test_remove_listing_for_raid_deletes_row_before_message(run, bot):
    raid_data = {"message_id": 11, "channel_id": 22, "guild_id": 33}
    order = []

    async def fake_remove(_bot, message_id):
        order.append(("table", message_id))

    async def fake_delete(channel_id, message_id):
        order.append(("message", channel_id, message_id))

    async def fake_sticky(_bot, _interaction, channel_id, guild_id):
        order.append(("sticky", channel_id, guild_id))

    bot.http.delete_message.side_effect = fake_delete
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


def test_remove_listing_for_raid_still_toggles_sticky_if_message_gone(run, bot):
    raid_data = {"message_id": 11, "channel_id": 22, "guild_id": 33}
    bot.http.delete_message.side_effect = discord.DiscordException("unknown message")
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


def test_remove_listing_for_raid_logs_sticky_errors(run, bot):
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


def test_remove_listing_for_lobby_noops_without_data(run, bot):
    with patch("handlers.raid_lobby_handler.RH.remove_listing_for_raid", new_callable=AsyncMock) as remove_listing:
        run(remove_listing_for_lobby(bot, None))
    remove_listing.assert_not_called()


def test_remove_listing_for_lobby_uses_raid_message_id(run, bot):
    lobby_data = {"raid_message_id": 99}
    with patch("handlers.raid_lobby_handler.RH.remove_listing_for_raid", new_callable=AsyncMock) as remove_listing:
        run(remove_listing_for_lobby(bot, lobby_data))
    remove_listing.assert_awaited_once_with(bot, 99)


def test_delete_lobby_removes_listing_then_channel(run, bot):
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


def test_guild_channel_delete_cleans_listing_for_lobby(run, bot, make_channel):
    channel = make_channel(7)
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


def test_guild_channel_delete_ignores_non_lobby_channels(run, bot, make_channel):
    channel = make_channel(8)
    with patch("handlers.events.deletions.RLH.get_lobby_data_by_lobby_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.events.deletions.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing, \
            patch("handlers.events.deletions.RLH.check_if_log_channel_and_purge_data", new_callable=AsyncMock) as purge:
        get_lobby.return_value = None
        run(deletions.on_guild_channel_delete(channel, bot))
    remove_listing.assert_not_called()
    purge.assert_awaited_once_with(bot, 8)


def test_host_close_deletes_lobby_when_channel_exists(run, bot, make_user):
    user = make_user()
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


def test_host_close_noops_when_user_is_not_hosting(run, bot, make_user):
    user = make_user()
    with patch("handlers.raid_lobby_management.RLH.get_lobby_data_by_user_id", new_callable=AsyncMock) as get_lobby, \
            patch("handlers.raid_lobby_management.RLH.delete_lobby", new_callable=AsyncMock) as delete, \
            patch("handlers.raid_lobby_management.RLH.remove_listing_for_lobby", new_callable=AsyncMock) as remove_listing:
        get_lobby.return_value = None
        run(host_manual_remove_lobby(bot, user))
    delete.assert_not_called()
    remove_listing.assert_not_called()
    user.send.assert_awaited_once()


def test_expiry_loop_removes_listing_if_lobby_channel_gone(run, bot):
    async def scenario():
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


def test_host_close_still_removes_listing_if_lobby_channel_missing(run, bot, make_user):
    user = make_user()
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


def test_trash_on_non_listing_does_not_dm(run, bot, make_user):
    user = make_user()
    message = SimpleNamespace(id=99, delete=AsyncMock())
    payload = SimpleNamespace(user_id=user.id, member=user, guild_id=1)
    with patch("handlers.events.reactions.RH.retrieve_raid_data_by_message_id", new_callable=AsyncMock, return_value=None):
        run(handle_reaction_remove_raid(bot, payload, message))
    user.send.assert_not_called()
    message.delete.assert_not_called()


def test_trash_on_listing_by_host_deletes_and_dms(run, bot, make_user):
    user = make_user()
    message = SimpleNamespace(id=42, delete=AsyncMock())
    payload = SimpleNamespace(user_id=user.id, member=user, guild_id=1)
    bot.get_guild = Mock(return_value=SimpleNamespace(name="Test Guild"))
    with patch(
        "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
        new_callable=AsyncMock,
        return_value={"user_id": user.id, "message_id": 42},
    ):
        run(handle_reaction_remove_raid(bot, payload, message))
    message.delete.assert_awaited_once()
    assert "successfuly deleted" in user.send.await_args.args[0]


def test_trash_still_dms_success_if_listing_delete_fails(run, bot, make_user):
    user = make_user()
    message = SimpleNamespace(id=42, delete=AsyncMock(side_effect=discord.DiscordException("unknown message")))
    payload = SimpleNamespace(user_id=user.id, member=user, guild_id=1)
    bot.get_guild = Mock(return_value=SimpleNamespace(name="Test Guild"))
    with patch(
        "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
        new_callable=AsyncMock,
        return_value={"user_id": user.id, "message_id": 42},
    ):
        run(handle_reaction_remove_raid(bot, payload, message))
    message.delete.assert_awaited_once()
    assert "successfuly deleted" in user.send.await_args.args[0]


def test_trash_on_listing_by_other_user_rejects(run, bot, make_user):
    user = make_user()
    message = SimpleNamespace(id=42, delete=AsyncMock())
    payload = SimpleNamespace(user_id=user.id, member=user, guild_id=1)
    bot.get_guild = Mock(return_value=SimpleNamespace(name="Test Guild"))
    with patch(
        "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
        new_callable=AsyncMock,
        return_value={"user_id": 999, "message_id": 42},
    ):
        run(handle_reaction_remove_raid(bot, payload, message))
    message.delete.assert_not_called()
    assert "not the host" in user.send.await_args.args[0]


def test_trash_uses_empty_guild_name_when_guild_is_missing(run, bot, make_user):
    user = make_user()
    message = SimpleNamespace(id=42, delete=AsyncMock())
    payload = SimpleNamespace(user_id=user.id, member=user, guild_id=1)
    bot.get_guild = Mock(return_value=None)
    with patch(
        "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
        new_callable=AsyncMock,
        return_value={"user_id": user.id, "message_id": 42},
    ):
        run(handle_reaction_remove_raid(bot, payload, message))
    message.delete.assert_awaited_once()
    assert "successfuly deleted" in user.send.await_args.args[0]


def test_trash_skips_dm_when_user_cannot_be_resolved(run, bot):
    message = SimpleNamespace(id=42, delete=AsyncMock())
    payload = SimpleNamespace(user_id=5, member=None, guild_id=1)
    bot.get_user = Mock(return_value=None)
    bot.fetch_user = AsyncMock(return_value=None)
    bot.get_guild = Mock(return_value=SimpleNamespace(name="Test Guild"))
    with patch(
        "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
        new_callable=AsyncMock,
        return_value={"user_id": 5, "message_id": 42},
    ):
        run(handle_reaction_remove_raid(bot, payload, message))
    message.delete.assert_awaited_once()


def add_trash_in_raid_channel(run, bot, user, message):
    bot.user = SimpleNamespace(id=99)
    bot.get_guild = Mock(return_value=SimpleNamespace(name="Test Guild"))
    message.author = SimpleNamespace(id=bot.user.id)
    message.guild = SimpleNamespace(id=1)
    channel = SimpleNamespace(
        id=100,
        type=discord.ChannelType.text,
        fetch_message=AsyncMock(return_value=message),
    )
    bot.retrieve_channel = AsyncMock(return_value=channel)
    payload = SimpleNamespace(
        user_id=user.id,
        member=user,
        guild_id=1,
        channel_id=100,
        message_id=message.id,
        emoji=SimpleNamespace(name="🗑️"),
    )
    with patch("handlers.events.reactions.RH.check_if_valid_raid_channel", new_callable=AsyncMock, return_value=True), \
            patch("handlers.events.reactions.REQH.check_if_valid_request_channel", new_callable=AsyncMock, return_value=False), \
            patch("handlers.events.reactions.RLH.get_raid_lobby_category_by_guild_id", new_callable=AsyncMock, return_value=None):
        run(raw_reaction_add_handle(payload, bot))


class TestTrashInRaidChannel:
    def test_bot_adding_trash_is_ignored(self, run, bot, make_user):
        user = make_user()
        bot.user = SimpleNamespace(id=user.id)
        message = SimpleNamespace(id=42, delete=AsyncMock(), author=SimpleNamespace(id=user.id))
        payload = SimpleNamespace(
            user_id=user.id,
            emoji=SimpleNamespace(name="🗑️"),
            channel_id=100,
            message_id=42,
        )
        run(raw_reaction_add_handle(payload, bot))
        user.send.assert_not_called()
        message.delete.assert_not_called()

    def test_trash_on_counters_does_not_dm_the_host(self, run, bot, make_user):
        user = make_user()
        counters = SimpleNamespace(id=50, delete=AsyncMock())
        with patch("handlers.events.reactions.RH.retrieve_raid_data_by_message_id", new_callable=AsyncMock, return_value=None):
            add_trash_in_raid_channel(run, bot, user, counters)
        user.send.assert_not_called()
        counters.delete.assert_not_called()

    def test_trash_on_listing_from_host_deletes_once(self, run, bot, make_user):
        user = make_user()
        listing = SimpleNamespace(id=42, delete=AsyncMock())
        with patch(
            "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
            new_callable=AsyncMock,
            return_value={"user_id": user.id, "message_id": 42},
        ):
            add_trash_in_raid_channel(run, bot, user, listing)
        listing.delete.assert_awaited_once()
        assert "successfuly deleted" in user.send.await_args.args[0]
        assert user.send.await_count == 1

    def test_trash_on_counters_then_listing_only_dms_success(self, run, bot, make_user):
        user = make_user()
        counters = SimpleNamespace(id=50, delete=AsyncMock())
        listing = SimpleNamespace(id=42, delete=AsyncMock())

        async def raid_for_message(_interaction, _bot, message_id):
            if int(message_id) == listing.id:
                return {"user_id": user.id, "message_id": listing.id}
            return None

        with patch("handlers.events.reactions.RH.retrieve_raid_data_by_message_id", side_effect=raid_for_message):
            add_trash_in_raid_channel(run, bot, user, counters)
            add_trash_in_raid_channel(run, bot, user, listing)

        counters.delete.assert_not_called()
        listing.delete.assert_awaited_once()
        assert user.send.await_count == 1
        assert "successfuly deleted" in user.send.await_args.args[0]

    def test_trash_on_listing_from_other_user_is_rejected(self, run, bot, make_user):
        user = make_user()
        listing = SimpleNamespace(id=42, delete=AsyncMock())
        with patch(
            "handlers.events.reactions.RH.retrieve_raid_data_by_message_id",
            new_callable=AsyncMock,
            return_value={"user_id": 999, "message_id": 42},
        ):
            add_trash_in_raid_channel(run, bot, user, listing)
        listing.delete.assert_not_called()
        assert "not the host" in user.send.await_args.args[0]
        assert user.send.await_count == 1


class TestReactionEarlyExits:
    def _payload(self, user_id=5, emoji_name="🗑️", message_id=42):
        return SimpleNamespace(
            user_id=user_id,
            member=None,
            guild_id=1,
            channel_id=100,
            message_id=message_id,
            emoji=SimpleNamespace(name=emoji_name),
        )

    def test_unknown_emoji_is_ignored(self, run, bot, make_user):
        bot.user = SimpleNamespace(id=99)
        bot.retrieve_channel = AsyncMock()
        run(raw_reaction_add_handle(self._payload(emoji_name="🔥"), bot))
        bot.retrieve_channel.assert_not_called()

    def test_missing_channel_is_ignored(self, run, bot):
        bot.user = SimpleNamespace(id=99)
        bot.retrieve_channel = AsyncMock(return_value=None)
        with patch("handlers.events.reactions.RH.check_if_valid_raid_channel", new_callable=AsyncMock, return_value=True), \
                patch("handlers.events.reactions.REQH.check_if_valid_request_channel", new_callable=AsyncMock, return_value=False):
            run(raw_reaction_add_handle(self._payload(), bot))

    def test_missing_message_is_ignored(self, run, bot):
        bot.user = SimpleNamespace(id=99)
        channel = SimpleNamespace(fetch_message=AsyncMock(side_effect=discord.DiscordException("unknown message")))
        bot.retrieve_channel = AsyncMock(return_value=channel)
        with patch("handlers.events.reactions.RH.check_if_valid_raid_channel", new_callable=AsyncMock, return_value=True), \
                patch("handlers.events.reactions.REQH.check_if_valid_request_channel", new_callable=AsyncMock, return_value=False):
            run(raw_reaction_add_handle(self._payload(), bot))

    def test_message_not_from_the_bot_is_ignored(self, run, bot, make_user):
        user = make_user()
        bot.user = SimpleNamespace(id=99)
        message = SimpleNamespace(id=42, author=SimpleNamespace(id=user.id), delete=AsyncMock())
        channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message), type=discord.ChannelType.text)
        bot.retrieve_channel = AsyncMock(return_value=channel)
        with patch("handlers.events.reactions.RH.check_if_valid_raid_channel", new_callable=AsyncMock, return_value=True), \
                patch("handlers.events.reactions.REQH.check_if_valid_request_channel", new_callable=AsyncMock, return_value=False):
            run(raw_reaction_add_handle(self._payload(user_id=user.id), bot))
        message.delete.assert_not_called()
        user.send.assert_not_called()

    def test_missing_reactor_is_ignored(self, run, bot):
        bot.user = SimpleNamespace(id=99)
        bot.get_user = Mock(return_value=None)
        bot.fetch_user = AsyncMock(return_value=None)
        message = SimpleNamespace(id=42, author=SimpleNamespace(id=99), delete=AsyncMock())
        channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message), type=discord.ChannelType.text)
        bot.retrieve_channel = AsyncMock(return_value=channel)
        with patch("handlers.events.reactions.RH.check_if_valid_raid_channel", new_callable=AsyncMock, return_value=True), \
                patch("handlers.events.reactions.REQH.check_if_valid_request_channel", new_callable=AsyncMock, return_value=False), \
                patch("handlers.events.reactions.handle_reaction_remove_raid", new_callable=AsyncMock) as remove_raid:
            run(raw_reaction_add_handle(self._payload(), bot))
        remove_raid.assert_not_called()
