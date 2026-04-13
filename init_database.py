import asyncio
import asyncpg
from os import environ
from dotenv import load_dotenv

load_dotenv()

RAIDS = """
CREATE TABLE IF NOT EXISTS raids(
  message_id BIGINT PRIMARY KEY,
  time_registered TIMESTAMP NOT NULL,
  guild_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  time_to_remove TIMESTAMP NOT NULL
);
"""

RAID_COUNTERS = """
CREATE TABLE IF NOT EXISTS guild_raid_counters(
  guild_id BIGINT PRIMARY KEY,
  raid_counter INT DEFAULT 0
);
"""
RAID_LOBBY_USER_MAP = """
DROP TABLE IF EXISTS raid_lobby_user_map;
CREATE TABLE IF NOT EXISTS raid_lobby_user_map (
  lobby_channel_id BIGINT PRIMARY KEY,
  host_user_id BIGINT NOT NULL,
  raid_message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  posted_at TIMESTAMP NOT NULL,
  delete_at TIMESTAMP NOT NULL,
  user_count INT NOT NULL,
  user_limit INT NOT NULL,
  applied_users INT NOT NULL,
  notified_users INT NOT NULL
);
"""

TRAINER_DATA = """
CREATE TABLE IF NOT EXISTS trainer_data(
  user_id BIGINT PRIMARY KEY,
  last_time_recalled TIMESTAMP NOT NULL,
  raids_hosted INT DEFAULT 0,
  friend_code CHAR(12),
  level INT,
  name VARCHAR(15),
  persistence INT DEFAULT 0,
  raids_participated_in INT DEFAULT 0
);
"""

RAID_APPLICATIONS = """
CREATE TABLE IF NOT EXISTS raid_application_user_map(
  user_id BIGINT PRIMARY KEY,
  raid_message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  is_requesting BOOLEAN NOT NULL,
  app_weight INT NOT NULL,
  has_been_notified BOOLEAN NOT NULL,
  checked_in BOOLEAN NOT NULL,
  activity_check_message_id BIGINT
);
"""

RAID_LOBBY_CATEGORY = """
CREATE TABLE IF NOT EXISTS raid_lobby_category(
  guild_id BIGINT PRIMARY KEY,
  category_id BIGINT NOT NULL,
  log_channel_id BIGINT NOT NULL
);
"""

REQUEST_CHANNELS = """
CREATE TABLE IF NOT EXISTS valid_requeset_channels(
  channel_id BIGINT PRIMARY KEY,
  guild_id BIGINT NOT NULL
);
"""
RECENT_PARTICIPATION_TABLE = """
CREATE TABLE IF NOT EXISTS raid_participation_table(
  user_id BIGINT PRIMARY KEY,
  last_participation_time TIMESTAMP NOT NULL
);
"""

REQUEST_TABLE = """
CREATE TABLE IF NOT EXISTS request_role_id_map(
  role_id BIGINT PRIMARY KEY,
  message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  role_name VARCHAR(20)
);
"""

RAID_STICKIES = """
CREATE TABLE IF NOT EXISTS raid_placeholder_stickies(
  channel_id BIGINT PRIMARY KEY,
  message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL
)
"""
async def main():
  conn = await asyncpg.connect(database='pogo_raid_bot',
                               port=5432,
                               host='localhost',
                               user='pi',
                               password=os.getenv('PASSWORD'))

  #await conn.execute(friend_code_table_update)
  #await conn.execute(UPDATE_WEIGHT_COLUMN)

asyncio.get_event_loop().run_until_complete(main())
