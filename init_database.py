import asyncio
import asyncpg
import os
from os import environ
from dotenv import load_dotenv

load_dotenv()
# For current ongoing raids
RAIDS = '''
CREATE TABLE IF NOT EXISTS raids(
  message_id BIGINT PRIMARY KEY,
  time_registered TIMESTAMPTZ NOT NULL,
  guild_id BIGINT NOT NULL,
  channel_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  time_to_remove TIMESTAMPTZ NOT NULL
);
'''
# For counting the amount of raids hosted
RAID_COUNTERS = '''
CREATE TABLE IF NOT EXISTS guild_raid_counters(
  guild_id BIGINT PRIMARY KEY,
  raid_counter INT DEFAULT 0
);
'''
# For logging the lobby data
RAID_LOBBY_USER_MAP = '''
DROP TABLE IF EXISTS raid_lobby_user_map;
CREATE TABLE IF NOT EXISTS raid_lobby_user_map (
  lobby_channel_id BIGINT PRIMARY KEY,
  host_user_id BIGINT NOT NULL,
  raid_message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  posted_at TIMESTAMPTZ NOT NULL,
  delete_at TIMESTAMPTZ NOT NULL,
  user_count INT NOT NULL,
  user_limit INT NOT NULL,
  applied_users INT NOT NULL,
  notified_users INT NOT NULL
);
'''

TRAINER_DATA = '''
CREATE TABLE IF NOT EXISTS trainer_data(
  user_id BIGINT PRIMARY KEY,
  last_time_recalled TIMESTAMPTZ NOT NULL,
  raids_hosted INT DEFAULT 0,
  friend_code CHAR(12),
  level INT,
  name VARCHAR(15),
  persistence INT DEFAULT 0,
  raids_participated_in INT DEFAULT 0
);
'''
# For trainers who are in the queue for the lobby
RAID_APPLICATIONS = '''
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
'''
# For setting the logging for each server
RAID_LOBBY_CATEGORY = '''
CREATE TABLE IF NOT EXISTS raid_lobby_category(
  guild_id BIGINT PRIMARY KEY,
  category_id BIGINT NOT NULL,
  log_channel_id BIGINT NOT NULL,
  management_channel_id BIGINT,
  management_message_id BIGINT
);
'''
# For setting the 
RAID_CHANNELS = '''
CREATE TABLE IF NOT EXISTS valid_raid_channels(
  channel_id BIGINT PRIMARY KEY,
  guild_id BIGINT NOT NULL
);
'''
# For for getting the tags to get pinged for a specifc pokemon
REQUEST_CHANNELS = '''
CREATE TABLE IF NOT EXISTS valid_request_channels(
  channel_id BIGINT PRIMARY KEY,
  guild_id BIGINT NOT NULL
);
'''
# For getting the user's last time they were a participant in a raid
RECENT_PARTICIPATION_TABLE = '''
CREATE TABLE IF NOT EXISTS raid_participation_table(
  user_id BIGINT PRIMARY KEY,
  last_participation_time TIMESTAMPTZ NOT NULL
);
'''
# For getting all of the message ids for giving out the tags for specific pokemon
REQUEST_TABLE = '''
CREATE TABLE IF NOT EXISTS request_role_id_map(
  role_id BIGINT PRIMARY KEY,
  message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL,
  role_name VARCHAR(20)
);
'''
# Uhhh to add some sort of messages to the top of channels or something? idk
RAID_STICKIES = '''
CREATE TABLE IF NOT EXISTS raid_placeholder_stickies(
  channel_id BIGINT PRIMARY KEY,
  message_id BIGINT NOT NULL,
  guild_id BIGINT NOT NULL
)
'''

# Existing databases may predate these columns; CREATE TABLE IF NOT EXISTS will not add them.
RAID_LOBBY_CATEGORY_MIGRATIONS = [
    'ALTER TABLE raid_lobby_category ADD COLUMN IF NOT EXISTS management_channel_id BIGINT;',
    'ALTER TABLE raid_lobby_category ADD COLUMN IF NOT EXISTS management_message_id BIGINT;',
]


async def initialize_database():
  conn = await asyncpg.connect(database=os.getenv('DATABASE'),
                               port=os.getenv('PORT'),
                               host=os.getenv('HOST'),
                               user=os.getenv('DB_USER'),
                               password=os.getenv('PASSWORD'))
  await conn.execute(RAIDS)
  await conn.execute(RAID_CHANNELS)
  await conn.execute(RAID_COUNTERS)
  await conn.execute(RAID_LOBBY_USER_MAP)
  await conn.execute(TRAINER_DATA)
  await conn.execute(RAID_APPLICATIONS)
  await conn.execute(RAID_LOBBY_CATEGORY)
  for migration in RAID_LOBBY_CATEGORY_MIGRATIONS:
    await conn.execute(migration)
  await conn.execute(REQUEST_CHANNELS)
  await conn.execute(RECENT_PARTICIPATION_TABLE)
  await conn.execute(REQUEST_TABLE)
  await conn.execute(RAID_STICKIES)
  #await conn.execute(friend_code_table_update)
  #await conn.execute(UPDATE_WEIGHT_COLUMN)
  await conn.close()
