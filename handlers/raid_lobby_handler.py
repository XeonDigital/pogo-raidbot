import asyncio
from datetime import datetime, timedelta

import asyncpg
import discord

import handlers.friend_code_handler as FCH
import handlers.helpers as H
import handlers.raid_handler as RH
import handlers.raid_lobby_management as RLM
from handlers.raid_handler import increment_raid_counter

async def create_raid_host_role(guild):
    try:
        return await guild.create_role(name="Raid Host", reason="Setting up a lobby system role.")
    except discord.DiscordException:
        pass

async def create_lobby_roles_for_guild(guild):
    try:
        await guild.create_role(name="Lobby Member", reason="Setting up a lobby system role.")
    except discord.DiscordException:
        pass
    try:
        await guild.create_role(name="Raid Moderator", reason="Setting up a lobby system role.")
    except discord.DiscordException:
        pass
    await create_raid_host_role(guild)


GET_CATEGORY_BY_GUILD_ID = """
    SELECT * FROM raid_lobby_category WHERE (guild_id = $1) LIMIT 1;
"""
async def get_raid_lobby_category_by_guild_id(bot, guild_id):
    try:
        category_data = await bot.database.fetchrow(GET_CATEGORY_BY_GUILD_ID,
                                                    int(guild_id))
    except asyncpg.PostgresError as error:
        print("[!] Error retreiving raid lobby category data. [{}]".format(error))
        return

    if not category_data:
        print("[!] Error retreiving raid lobby category data. [{}]".format("No category found. Ignoring."))
        return

    return category_data


GET_LOBBY_BY_USER_ID = """
    SELECT * FROM raid_lobby_user_map WHERE (host_user_id = $1);
"""
async def get_lobby_data_by_user_id(bot, user_id):
    return await bot.database.fetchrow(GET_LOBBY_BY_USER_ID,
                                       int(user_id))

async def get_lobby_channel_for_user_by_id(bot, user_id):
    try:
        lobby_data = await bot.database.fetchrow(GET_LOBBY_BY_USER_ID,
                                                 int(user_id))
    except asyncpg.PostgresError as error:
        print("[!] Error retreiving raid lobby data. [{}]".format(error))
        return

    if not lobby_data:
        return

    lobby_channel_id = lobby_data.get("lobby_channel_id")
    lobby = bot.get_channel(int(lobby_channel_id))
    if not lobby:
        try:
            lobby = await bot.fetch_channel(int(lobby_channel_id))
            print(lobby)
        except discord.NotFound:
            await remove_lobby_by_lobby_id(bot, lobby_channel_id)
            return
        except discord.DiscordException as error:
            print(f"[!] Error fetching channel [{error}]")
            return

    return lobby

GET_LOBBY_BY_LOBBY_ID = """
    SELECT * FROM raid_lobby_user_map WHERE (lobby_channel_id = $1);
"""
async def get_lobby_channel_by_lobby_id(bot, channel_id):
    try:
        lobby_data = await bot.database.fetchrow(GET_LOBBY_BY_LOBBY_ID,
                                                 int(channel_id))
    except asyncpg.PostgresError as error:
        print("[!] Error retreiving raid lobby data. [{}]".format(error))
        return

    if not lobby_data:
        return False

    lobby_channel_id = lobby_data.get("lobby_channel_id")

    lobby = bot.get_channel(int(lobby_channel_id))
    if not lobby:
        return False
    lobby.lobby_data = lobby_data
    return lobby

GET_RELEVANT_LOBBY_BY_TIME_AND_USERS = """
    SELECT * FROM raid_lobby_user_map
    WHERE (user_count < user_limit)
    ORDER BY posted_at;
"""
async def get_latest_lobby_data_by_timestamp(bot):
    return await bot.database.fetch(GET_RELEVANT_LOBBY_BY_TIME_AND_USERS)

async def log_message_in_raid_lobby_channel(bot, message, lobby_channel, lobby_data):
    author = message.author
    category_data = await get_raid_lobby_category_by_guild_id(bot, message.guild.id)
    log_channel_id = category_data.get("log_channel_id")
    log_channel = bot.get_channel(int(log_channel_id))

    new_embed = discord.Embed(title="Logged Message", url=message.jump_url, description=message.content)
    new_embed.set_author(name=author.name, icon_url=author.avatar_url)
    new_embed.set_footer(text=f"User ID: {author.id} | Time: {datetime.utcnow()} UTC")
    host_user_id = lobby_data.get("host_user_id")
    guild = lobby_channel.guild
    host_member = discord.utils.get(guild.members, id=host_user_id)
    await log_channel.send(f"Lobby: {lobby_channel.name}\nHost: {host_member.mention}", embed=new_embed)

NEW_LOBBY_INSERT = """
INSERT INTO raid_lobby_user_map (lobby_channel_id, host_user_id, raid_message_id, guild_id, posted_at, delete_at, user_count, user_limit, applied_users, notified_users)
VALUES($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
"""
async def add_lobby_to_table(bot, lobby_channel_id, host_user_id, raid_id, guild_id, delete_at, invite_slots):
    """Add a raid to the database with all the given data points."""
    cur_time = datetime.now()
    await bot.database.execute(NEW_LOBBY_INSERT,
                               int(lobby_channel_id),
                               int(host_user_id),
                               int(raid_id),
                               int(guild_id),
                               cur_time,
                               delete_at,
                               0,
                               int(invite_slots),
                               0,
                               0)

async def create_raid_lobby(ctx, bot, raid_message_id, raid_host_member, time_to_remove_lobby, invite_slots) -> discord.TextChannel:
    guild = ctx.guild
    raid_lobby_category_channel_data = await get_raid_lobby_category_by_guild_id(bot, guild.id)
    if not raid_lobby_category_channel_data:
        return False
    raid_lobby_category_channel_id = raid_lobby_category_channel_data.get("category_id")
    raid_lobby_category_channel = bot.get_channel(int(raid_lobby_category_channel_id))

    raid_moderator_role = discord.utils.get(guild.roles, name="Raid Moderator")
    lobby_member_role = discord.utils.get(guild.roles, name="Lobby Member")
    muted_role = discord.utils.get(guild.roles, name="Muted")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        raid_host_member: discord.PermissionOverwrite(read_messages=True,
                                                      #send_messages=True,
                                                      embed_links=True,
                                                      attach_files=True),
        bot.user: discord.PermissionOverwrite(read_messages=True,
                                              send_messages=True,
                                              embed_links=True,
                                              manage_channels=True,
                                              manage_messages=True)
    }

    if raid_moderator_role:
        overwrites.update({raid_moderator_role: discord.PermissionOverwrite(read_messages=True)})

    if muted_role:
        overwrites.update({muted_role:discord.PermissionOverwrite(send_messages=False)})

    # count = await RH.get_raid_count(bot, ctx, False)
    # channel_name = "raid-lobby-{}".format(await RH.get_raid_count(bot, ctx, False))

    reason = "Spawning new raid lobby for [{}]".format(raid_host_member.name)
    try:
        new_raid_lobby = await raid_lobby_category_channel.create_text_channel("raid-lobby-{}".format(await RH.get_raid_count(bot, ctx, False)), reason=reason, overwrites=overwrites)
        #await increment_raid_counter(ctx, bot, ctx.guild.id)
    except discord.DiscordException as error:
        try:
            await ctx.send("Something went wrong when trying to create your raid lobby: [{}]".format(error), delete_after=15)
        except discord.DiscordException:
            pass
        print("[!] An error occurred creating a raid lobby. [{}]".format(error))
        return False
    except AttributeError as error:
        try:
            await ctx.send("Something went wrong when trying to create your raid lobby: [{}]".format(error), delete_after=15)
        except discord.DiscordException:
            pass
        print("[!] An error occurred creating a raid lobby. [{}]".format(error))
        return False

    new_embed = discord.Embed(title="Start of Lobby", description="Welcome to your raid lobby. As players apply they will check in and be added here.\n\nAs the host it is your job to ensure you either add everyone, or everyone adds you. Once you have everyone in your friends list, then it is up to you to invite the players who join this lobby into your raid in game.")

    friend_code, has_code = await FCH.get_friend_code(bot, raid_host_member.id, host=True)
    header_message_body = f"{friend_code}\n{raid_host_member.mention}\n"

    try:
        header_message_body = header_message_body + "Ping the role {} for managing all members of this lobby at once.".format(lobby_member_role.mention)
    except AttributeError as error:
        pass

    if has_code:
        new_embed.set_footer(text="You can copy this message directly into the game.")

    message = await new_raid_lobby.send(header_message_body, embed=new_embed)
    try:
        await message.pin()
    except discord.DiscordException:
        pass
    try:
        await add_lobby_to_table(bot, new_raid_lobby.id, raid_host_member.id, raid_message_id, ctx.guild.id, time_to_remove_lobby, invite_slots)
    except asyncpg.PostgresError as error:
        print("[!] An error occurred adding a lobby to the database. [{}]".format(error))
        await new_raid_lobby.delete()
        return

    role = discord.utils.get(guild.roles, name="Raid Host")
    if not role:
        role = await create_raid_host_role(guild)

    await bot.add_role_ignore_error(raid_host_member, role, "Giving raid host the raid host role.")

    #await RLM.give_member_management_channel_view_permissions(bot, raid_lobby_category_channel_data, raid_host_member)

    bot.lobby_remove_trigger.set()

    return new_raid_lobby

UPDATE_TIME_TO_REMOVE_LOBBY = """
    UPDATE raid_lobby_user_map
    SET delete_at = $1
    WHERE (raid_message_id = $2);
"""
async def update_delete_time_with_given_time(bot, new_time, raid_id):
    bot.lobby_remove_trigger.set()
    return await bot.database.execute(UPDATE_TIME_TO_REMOVE_LOBBY,
                                       new_time,
                                       int(raid_id))

async def alter_deletion_time_for_raid_lobby(bot, raid_id):
    current_time = datetime.now()
    lobby_data = await get_lobby_data_by_raid_id(bot, raid_id)

    if not lobby_data:
        return

    lobby_channel_id = lobby_data.get("lobby_channel_id")
    lobby = bot.get_channel(int(lobby_channel_id))
    if not lobby:
        try:
            lobby = await bot.fetch_channel(int(lobby_channel_id))
        except discord.DiscordException:
            pass

    users = lobby_data.get("user_count")
    new_delete_time = current_time if users == 0 else current_time + timedelta(minutes=15)

    await bot.database.execute(UPDATE_TIME_TO_REMOVE_LOBBY,
                               new_delete_time,
                               int(lobby_data.get("raid_message_id")))
    limit = lobby_data.get("user_limit")
    try:
        if lobby and users > 0:
            if users < limit:
                new_embed = discord.Embed(title=f"{users}/{limit}", description="This lobby will expire in 15 minutes. Use -extend to add time as needed.\n\nNo new members will be added to this lobby.\n\nIf there are not enough players to complete this raid, please don’t waste any time or passes attempting unless you are confident you can complete the raid with a smaller group.")
            else:
                new_embed = discord.Embed(title=f"{users}/{limit} FULL", description="This lobby will expire in 15 minutes. Use -extend to add time as needed.\n\nThe lobby is now full. All players have checked in. The raid listing has been removed.")

            new_embed.set_footer(text="If you have any feedback or questions about this bot, reach out to TheStaplergun#6920")
            await lobby.send(" ", embed=new_embed)
    except discord.DiscordException:
        pass

GET_NEXT_LOBBY_TO_REMOVE_QUERY = """
    SELECT * FROM raid_lobby_user_map
    ORDER BY delete_at
    LIMIT 1;
"""
async def get_next_lobby_to_remove(bot):
    return await bot.database.fetchrow(GET_NEXT_LOBBY_TO_REMOVE_QUERY)

UPDATE_APPLICATION_DATA_FOR_USER = """
    UPDATE raid_application_user_map
    SET raid_message_id = $1
    WHERE (user_id = $2);
"""
async def update_application_for_user(bot, member, raid_message_id):
    await bot.database.execute(UPDATE_APPLICATION_DATA_FOR_USER,
                               int(raid_message_id),
                               int(member.id))

    try:
        new_embed = discord.Embed(title="System Notification", description="You have updated your application to the selected raid.")
        await member.send(" ", embed=new_embed)
    except discord.DiscordException:
        pass

REMOVE_APPLICATION_FOR_USER_BY_ID = """
    DELETE FROM raid_application_user_map WHERE (user_id = $1)
    RETURNING raid_message_id;
"""
REDUCE_APPLICANT_COUNT_BY_RAID_ID = """
    UPDATE raid_lobby_user_map
    SET applied_users = applied_users - 1
    WHERE (raid_message_id = $1);
"""
async def remove_application_for_user(bot, member, raid_id):
    async with bot.database.connect() as c:
        await c.execute(REMOVE_APPLICATION_FOR_USER_BY_ID, member.id)
        await c.execute(REDUCE_APPLICANT_COUNT_BY_RAID_ID, raid_id)

    try:
        new_embed = discord.Embed(title="System Notification", description="You have withdrawn your application to the selected raid.")
        await member.send(" ", embed=new_embed)
    except discord.DiscordException:
        pass


async def handle_manual_clear_application(ctx, user_id, bot):
    result = await bot.database.execute(REMOVE_APPLICATION_FOR_USER_BY_ID, int(user_id))
    try:
        await ctx.send(result)
    except discord.DiscordException:
        pass

INSERT_NEW_APPLICATION_DATA = """
    INSERT INTO raid_application_user_map (user_id, raid_message_id, guild_id, is_requesting, app_weight, has_been_notified, checked_in)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
"""
UPDATE_LOBBY_APPLICANT_DATA = """
    UPDATE raid_lobby_user_map
    SET applied_users = applied_users + 1
    WHERE (raid_message_id = $1);
"""
async def insert_new_application(bot, user_id, raid_message_id, guild_id, is_requesting, app_weight):
    try:
        await bot.database.execute(INSERT_NEW_APPLICATION_DATA,
                                   int(user_id),
                                   int(raid_message_id),
                                   int(guild_id),
                                   is_requesting,
                                   app_weight,
                                   False,
                                   False)
    except asyncpg.PostgresError as error:
        pass

async def calculate_speed_bonus(message, listing_duration):
    creation_time = message.created_at
    time_difference = (datetime.now() - creation_time)
    return 100 - (time_difference.total_seconds() / listing_duration * 100) # Calculated by quickness of application over total life of raid listing.

async def handle_new_application(ctx, bot, member, message, channel):
    raid_data = await RH.retrieve_raid_data_by_message_id(ctx, bot, message.id)
    if not raid_data:
        return False
    _, pokemon_name = H.get_pokemon_name_from_raid(message)
    host_id = raid_data.get("user_id")

    try:
        if host_id == member.id:
            new_embed = discord.Embed(title="Error", description="You cannot apply to your own raid!")
            await member.send(" ", embed=new_embed)
            return False
        else:
            new_embed = discord.Embed(title="System Notification", description="You have applied for the selected raid.\nApplicants will be selected at random based on a weighted system.\n\nYou will be sent a DM here to check in if you are selected. You only have 30 seconds to check in once you are selected.\n\nYou will know within 60 seconds if you are selected, unless another user fails to check in, then it may be longer.")
            await member.send(" ", embed=new_embed)
    except discord.Forbidden:
        # Prevents users from applying without ability to send a DM.
        new_embed = discord.Embed(title="Communication Error", description="{}, I cannot DM you. You will not be able to apply for raids until I can.".format(member.mention))
        await channel.send(" ", embed=new_embed, delete_after=15)
        return False
    role = discord.utils.get(member.roles, name=pokemon_name)
    time_to_end = raid_data.get("time_to_remove")
    listing_duration = time_to_end - message.created_at
    speed_bonus = await calculate_speed_bonus(message, listing_duration.total_seconds())
    app_weight = await calculate_weight(bot, True if role else False, speed_bonus, member.id)
    await insert_new_application(bot, member.id, message.id, message.guild.id, (True if role else False), app_weight)
    bot.applicant_trigger.set()

QUERY_APPLICATION_DATA_FOR_USER = """
    SELECT * FROM raid_application_user_map WHERE (user_id = $1);
"""
async def get_applicant_data_for_user(bot, user_id):
    return await bot.database.fetchrow(QUERY_APPLICATION_DATA_FOR_USER, user_id)

async def handle_application_to_raid(bot, ctx, message, channel):
    guild = message.guild
    member = guild.get_member(ctx.user_id)
    result = await get_applicant_data_for_user(bot, ctx.user_id)

    if result:
        applied_to_raid_id = result.get("raid_message_id")
        has_been_notified = result.get("has_been_notified")
        if has_been_notified:
            new_embed = discord.Embed(title="Error", description="You are already locked into a raid. Wait until that raid is complete.")
            await member.send(" ", embed=new_embed)
            return
        raid_message_id = message.id
        if applied_to_raid_id == raid_message_id:
            await remove_application_for_user(bot, member, applied_to_raid_id)
        else:
            await update_application_for_user(bot, member, applied_to_raid_id)
    else:
        await handle_new_application(ctx, bot, member, message, channel)

QUERY_APPLICANT_BY_MESSAGE_ID = """
    SELECT * FROM raid_application_user_map WHERE (activity_check_message_id = $1);
"""
async def get_applicant_data_by_message_id(bot, message_id):
    return await bot.database.fetchrow(QUERY_APPLICANT_BY_MESSAGE_ID, message_id)

GET_USERS_BY_RAID_MESSAGE_ID = """
    SELECT * FROM raid_application_user_map
    WHERE (raid_message_id = $1 and has_been_notified = FALSE)
    ORDER BY app_weight DESC;
"""
"""
    LIMIT $2;
"""
async def get_applicants_by_raid_id(bot, raid_message_id):#, user_limit):
    return await bot.database.fetch(GET_USERS_BY_RAID_MESSAGE_ID, int(raid_message_id))#, int(user_limit))

QUERY_RECENT_PARTICIPATION = """
    SELECT * FROM raid_participation_table WHERE (user_id = $1);
"""
GET_PERSISTENCE_BONUS = """
    SELECT * FROM trainer_data WHERE (user_id = $1);
"""
async def calculate_weight(bot, is_requesting, speed_bonus_weight, member_id):
#async def calculate_weight(bot, user_data, member_id):
    async with bot.database.connect() as c:
        result = await c.fetchrow(QUERY_RECENT_PARTICIPATION, int(member_id))
        persistence = await c.fetchrow(GET_PERSISTENCE_BONUS, int(member_id))

    recent_participation_weight = 100
    #is_requesting = user_data.get("is_requesting")
    #speed_bonus_weight = user_data.get("speed_bonus_weight")
    persistence_weight = persistence.get("persistence") if persistence else 0
    persistence_weight = persistence_weight+(5*persistence_weight**2)
    if result:
        last_participation_time = result.get("last_participation_time")
        current_time = datetime.now()
        time_difference = current_time - last_participation_time
        if time_difference.total_seconds() < 3600:
            recent_participation_weight = (time_difference.total_seconds()/3600) * 100
    return recent_participation_weight + (100 if is_requesting else 0) + speed_bonus_weight + persistence_weight

UPDATE_LOBBY_APPLICANT_DATA = """
    UPDATE raid_application_user_map
    SET has_been_notified = true,
        activity_check_message_id = $1
    WHERE (user_id = $2);
"""

async def set_notified_flag(bot, message_id, user_id):
    await bot.database.execute(UPDATE_LOBBY_APPLICANT_DATA, int(message_id), int(user_id))

INCREMENT_APPLICANT_COUNT = """
    UPDATE raid_lobby_user_map
    SET notified_users = notified_users + 1
    WHERE (lobby_channel_id = $1)
"""
async def increment_notified_users_for_raid_lobby(bot, lobby_id):
    await bot.database.execute(INCREMENT_APPLICANT_COUNT, int(lobby_id))

async def process_user_list(bot, raid_lobby_data, users, guild):
    counter = 1
    current_count = raid_lobby_data.get("user_count")
    user_limit = raid_lobby_data.get("user_limit")
    notified_count = raid_lobby_data.get("notified_users")

    total_pending = notified_count + current_count
    current_needed = user_limit - total_pending

    for user in users:
        if counter > current_needed:
            break
        member = guild.get_member(int(user.get("user_id")))#user["member_object"]
        if not member:
            continue
        try:
            new_embed = discord.Embed(title="Activity Check", description="Tap the reaction below to confirm you are present. This message will expire in 30 seconds.")
            message = await member.send(" ", embed=new_embed, delete_after=30)
        except discord.DiscordException:
            try:
                await message.delete()
            except:
                pass
            continue
        try:
            await message.add_reaction("⏱️")
        except discord.DiscordException:
            try:
                await message.delete()
            except:
                pass
            continue
        await set_notified_flag(bot, message.id, member.id)
        await increment_notified_users_for_raid_lobby(bot, raid_lobby_data.get("lobby_channel_id"))
        counter+=1

QUERY_LOBBY_BY_RAID_ID = """
    SELECT * FROM raid_lobby_user_map WHERE (raid_message_id = $1)
"""
async def get_lobby_data_by_raid_id(bot, raid_id):
    return await bot.database.fetchrow(QUERY_LOBBY_BY_RAID_ID, int(raid_id))

UPDATE_USER_COUNT_FOR_RAID_LOBBY = """
    UPDATE raid_lobby_user_map
    SET user_count = user_count + 1,
        notified_users = notified_users - 1
    WHERE (lobby_channel_id = $1);
"""
async def increment_user_count_for_raid_lobby(bot, lobby_id):
    await bot.database.execute(UPDATE_USER_COUNT_FOR_RAID_LOBBY, int(lobby_id))

UPDATE_CHECKED_IN_FLAG = """
    UPDATE raid_application_user_map
    SET checked_in = true
    WHERE (user_id = $1);
"""
RESET_PERSISTENCE_INCREMENT_PARTICPATED = """
    UPDATE trainer_data
    SET persistence = 0,
        raids_participated_in = raids_participated_in + 1
    WHERE (user_id = $1);
"""
async def set_checked_in_flag(bot, user_id):
    async with bot.database.connect() as c:
        await c.execute(UPDATE_CHECKED_IN_FLAG, int(user_id))
        await c.execute(RESET_PERSISTENCE_INCREMENT_PARTICPATED, int(user_id))

DELETE_RECENT_PARTICIPATION_RECORD = """
    DELETE FROM raid_participation_table WHERE (user_id = $1);
"""
UDPATE_RECENT_PARTICIPATION = """
    INSERT INTO raid_participation_table(user_id, last_participation_time)
    VALUES ($1, $2);
"""
async def set_recent_participation(bot, user_id):
    async with bot.database.connect() as c:
        await c.execute(DELETE_RECENT_PARTICIPATION_RECORD, int(user_id))
        await c.execute(UDPATE_RECENT_PARTICIPATION, int(user_id), datetime.now())

async def check_if_lobby_full(bot, lobby_id):
    lobby_data = await bot.database.fetchrow(GET_LOBBY_BY_LOBBY_ID, int(lobby_id))
    if lobby_data.get("user_count") == lobby_data.get("user_limit"):
        await RH.delete_raid(bot, lobby_data.get("raid_message_id"))

async def process_and_add_user_to_lobby(bot, member, lobby, guild, message, lobby_data):
    role = discord.utils.get(guild.roles, name="Lobby Member")
    friend_code, has_code = await FCH.get_friend_code(bot, member.id)
    users = lobby_data.get("user_count")
    limit = lobby_data.get("user_limit")
    if has_code:
        message_to_send = f"{friend_code} **<-Friend Code**\n{member.mention} **{users+1}/{limit}** checked in."
        message_to_send = f"{message_to_send}\n*Copy this message directly into the game.*\n-----"
    else:
        message_to_send = f"{friend_code}\n{member.mention} **{users+1}/{limit}** checked in.\n-----"

    await asyncio.gather(increment_user_count_for_raid_lobby(bot, lobby.id),
                         set_checked_in_flag(bot, member.id),
                         lobby.set_permissions(member, read_messages=True,
                                                       #send_messages=True,
                                                       embed_links=True,
                                                       attach_files=True),
                         set_recent_participation(bot, member.id),
                         bot.add_role_ignore_error(member, role, "Member of lobby"),
                         bot.send_ignore_error(member, f"You have been selected for the raid and added to the lobby. **The hosts information is pinned in the channel.** Click this for a shortcut to the lobby: {lobby.mention}"),
                         bot.send_ignore_error(lobby, message_to_send),
                         bot.delete_ignore_error(message))

    await check_if_lobby_full(bot, lobby.id)


async def handle_activity_check_reaction(ctx, bot, message):
    result = await bot.database.fetchrow(QUERY_APPLICATION_DATA_FOR_USER, ctx.user_id)
    if not result:
        return

    activity_check_message_id = result.get("activity_check_message_id")
    if not message.id == activity_check_message_id:
        return

    raid_message_id = result.get("raid_message_id")

    lobby_data = await get_lobby_data_by_raid_id(bot, raid_message_id)
    if not lobby_data:
        return
    lobby_id = lobby_data.get("lobby_channel_id")
    lobby = bot.get_channel(int(lobby_id))

    guild = lobby.guild
    user_id = ctx.user_id
    member = guild.get_member(int(user_id))
    await process_and_add_user_to_lobby(bot, member, lobby, guild, message, lobby_data)

GET_LOBBY_BY_LOBBY_ID = """
    SELECT * FROM raid_lobby_user_map WHERE (lobby_channel_id = $1);
"""
async def get_lobby_data_by_lobby_id(bot, lobby_id):
    return await bot.database.fetchrow(GET_LOBBY_BY_LOBBY_ID, int(lobby_id))

PURGE_APPLICANTS_FOR_RAID = """
    DELETE FROM raid_application_user_map WHERE (raid_message_id = $1);
"""
async def remove_applicants_for_raid_by_raid_id(bot, raid_id):
    await bot.database.execute(PURGE_APPLICANTS_FOR_RAID, raid_id)

REMOVE_LOBBY_BY_ID = """
    DELETE FROM raid_lobby_user_map WHERE (lobby_channel_id = $1);
"""
async def remove_lobby_by_lobby_id(bot, lobby_data):
    if lobby_data:
        raid_id = lobby_data.get("raid_message_id")
        await remove_applicants_for_raid_by_raid_id(bot, raid_id)

    await bot.database.execute(REMOVE_LOBBY_BY_ID, int(lobby_data.get("lobby_channel_id")))

SELECT_ALL_LOBBIES = """
    SELECT * FROM raid_lobby_user_map;
"""
async def get_all_lobbies(bot):
    return await bot.database.fetch(SELECT_ALL_LOBBIES)

SELECT_ALL_APPLICATIONS = """
    SELECT * FROM raid_application_user_map;
"""
async def get_all_applications(bot):
    return await bot.database.fetch(SELECT_ALL_APPLICATIONS)

REMOVE_LOG_CHANNEL_BY_ID = """
    DELETE FROM raid_lobby_category WHERE (log_channel_id = $1);
"""
async def check_if_log_channel_and_purge_data(bot, channel_id):
    await bot.database.execute(REMOVE_LOG_CHANNEL_BY_ID, int(channel_id))

DECREMENT_NOTIFIED_USERS = """
    UPDATE raid_lobby_user_map
    SET notified_users = notified_users - 1
    WHERE (raid_message_id = $1)
"""
async def decrement_notified_users_by_raid_id(bot, raid_id):
    await bot.database.execute(DECREMENT_NOTIFIED_USERS, int(raid_id))

async def handle_user_failed_checkin(bot, applicant_data):
    guild_id = applicant_data.get("guild_id")
    guild = bot.get_guild(int(guild_id))

    member = guild.get_member(applicant_data.get("user_id"))
    if not member:
        return False
    raid_id = applicant_data.get("raid_message_id")
    new_embed = discord.Embed(title="System Notification", description="You failed to check in and have been removed.")
    await asyncio.gather(remove_application_for_user(bot, member, raid_id),
                         decrement_notified_users_by_raid_id(bot, raid_id),
                         bot.send_ignore_error(member, " ", embed=new_embed))

async def delete_lobby(bot, lobby):
    members = lobby.members
    guild = lobby.guild
    lobby_member_role = discord.utils.get(guild.roles, name="Lobby Member")
    raid_host_role = discord.utils.get(guild.roles, name="Raid Host")
    new_embed = discord.Embed(title="System Notification", description="This lobby has been flagged for removal or has expired and is in the process of being shut down.")
    try:
        await lobby.send(embed=new_embed)
    except discord.DiscordException:
        pass

    tasks = []
    for member in members:
        if discord.utils.get(member.roles, name="Lobby Member"):
            tasks.append(bot.remove_role_ignore_error(member, lobby_member_role, "End of Raid"))
        if discord.utils.get(guild.roles, name="Raid Host"):
            tasks.append(bot.remove_role_ignore_error(member, raid_host_role, "End of Raid"))
    tasks.append(bot.delete_ignore_error(lobby))

    await asyncio.gather(*tasks)

async def handle_admin_close_lobby(ctx, bot, lobby_id):
    if lobby_id == "":
        lobby_id = ctx.channel.id
    lobby_data = await get_lobby_data_by_lobby_id(bot, lobby_id)

    if lobby_data and lobby_id == ctx.channel.id:
        lobby = ctx.channel
    else:
        lobby = await bot.retrieve_channel(lobby_id)

    if lobby and not lobby.permissions_for(ctx.author).manage_channels:
        embed = discord.Embed(title="", description="You do not have permission to manage that lobby.")
        await bot.send_ignore_error(ctx, "", embed=embed, delete_after=15)
        return False

    if lobby_data and lobby_data.get("lobby_channel_id") != lobby_id:
        await bot.send_ignore_error(ctx, "The given channel id is not a valid lobby.", delete_after=15)

    if not lobby:
        try:
            await ctx.send("The given channel id is not a valid lobby.")
        except discord.DiscordException:
            return

    try:
        embed = discord.Embed(title="", description="The lobby is being shut down.")
        message = await ctx.send(embed=embed)
    except discord.DiscordException:
        pass
    await delete_lobby(bot, lobby)
    if lobby_data and lobby_id != ctx.channel.id:
        try:
            embed = discord.Embed(title="", description="The requested lobby has been removed.")
            await message.edit(embed=embed)
        except discord.DiscordException:
            pass
