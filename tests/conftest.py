import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
formats_py = ROOT / "data" / "formats.py"
formats_example = ROOT / "data" / ".formats.py"
if not formats_py.exists() and formats_example.exists() and "data.formats" not in sys.modules:
    spec = importlib.util.spec_from_file_location("data.formats", formats_example)
    module = importlib.util.module_from_spec(spec)
    sys.modules["data.formats"] = module
    spec.loader.exec_module(module)


CHANNEL_ID = 100
USER_ID = 5
GUILD_ID = 1
GUILD_NAME = "Test Guild"
CURRENT_RAID_BOSSES = {"Mewtwo"}


@pytest.fixture
def run():
    return asyncio.run


@pytest.fixture
def followup_text():
    def text(interaction):
        args = interaction.followup.send.await_args.args
        return args[0] if args else ""

    return text


@pytest.fixture
def make_user():
    def factory(user_id=USER_ID, roles=None):
        return SimpleNamespace(
            id=user_id,
            name="tester",
            mention=f"<@{user_id}>",
            roles=[] if roles is None else roles,
            send=AsyncMock(),
        )

    return factory


@pytest.fixture
def make_channel():
    def factory(channel_id=CHANNEL_ID):
        channel = SimpleNamespace(id=channel_id, send=AsyncMock())
        channel.send.return_value = SimpleNamespace(
            id=42,
            content="",
            channel=channel,
            add_reaction=AsyncMock(),
            edit=AsyncMock(),
        )
        return channel

    return factory


@pytest.fixture
def make_guild():
    def factory(guild_id=GUILD_ID, name=GUILD_NAME):
        return SimpleNamespace(id=guild_id, name=name)

    return factory


@pytest.fixture
def make_interaction(make_channel, make_user, make_guild):
    def factory(channel=None, user=None, guild=None):
        return SimpleNamespace(
            channel=channel or make_channel(),
            user=user or make_user(),
            guild=guild or make_guild(),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    return factory


@pytest.fixture
def make_bot():
    def factory(raid_channel_ids=None, categories_allowed=True):
        return SimpleNamespace(
            raid_channel_cache=set() if raid_channel_ids is None else set(raid_channel_ids),
            request_channel_cache=set(),
            database=SimpleNamespace(
                fetchrow=AsyncMock(return_value=None),
                execute=AsyncMock(),
                fetch=AsyncMock(return_value=[]),
            ),
            send_ignore_error=AsyncMock(),
            retrieve_channel=AsyncMock(return_value=None),
            delete_ignore_error=AsyncMock(),
            remove_role_ignore_error=AsyncMock(),
            http=SimpleNamespace(delete_message=AsyncMock()),
            categories_allowed=categories_allowed,
            lobby_remove_trigger=asyncio.Event(),
            dex=SimpleNamespace(
                is_current_raid_boss=Mock(side_effect=lambda name: name in CURRENT_RAID_BOSSES),
            ),
        )

    return factory


@pytest.fixture
def bot(make_bot):
    return make_bot()


@pytest.fixture
def interaction(make_interaction):
    return make_interaction()


@pytest.fixture
def make_context(make_interaction, make_bot, make_user):
    def factory(raid_channel=True, verified=False):
        roles = [SimpleNamespace(name="Verified Raid Host")] if verified else None
        interaction = make_interaction(user=make_user(roles=roles))
        channel_ids = {interaction.channel.id} if raid_channel else set()
        return interaction, make_bot(raid_channel_ids=channel_ids)

    return factory
