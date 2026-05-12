"""Raid SQL statements and database interaction functions"""
from datetime import datetime, timedelta

import asyncpg
import discord

import handlers.helpers as H
#import handlers.raid_lobby_handler as RLH
import handlers.request_handler as REQH
import handlers.sticky_handler as SH
from pogo_raid_lib import validate_and_format_message

NEW_RAID_INSERT = """
INSERT INTO raids(message_id, time_registered, guild_id, channel_id, user_id, time_to_remove)
VALUES($1, $2, $3, $4, $5, $6)
"""
async def add_raid_to_table(interaction: discord.Interaction, bot, message_id, guild_id, channel_id, user_id, time_to_remove):
    """Add a raid to the database with all the given data points."""
    cur_time = datetime.now()

    await bot.database.execute(NEW_RAID_INSERT,
                                 int(message_id),
                                 cur_time,
                                 int(guild_id),
                                 int(channel_id),
                                 int(user_id),
                                 time_to_remove)


INCREMENT_RAID_UPDATE_STATEMENT = """
UPDATE guild_raid_counters
SET raid_counter = $2
WHERE (guild_id = $1);
"""
async def increment_raid_counter(interaction: discord.Interaction, bot, guild_id):
    """Increments raid counter for a server for statistics tracking."""
    bot.guild_raid_counters[guild_id] += 1
    await bot.database.execute(INCREMENT_RAID_UPDATE_STATEMENT, guild_id, bot.guild_raid_counters[guild_id])

GET_RAID_COUNT_STATEMENT = """
    SELECT * FROM guild_raid_counters WHERE (guild_id = $1) LIMIT 1;
"""
async def get_raid_count(bot, interaction: discord.Interaction, should_print):
    """Get raid count for server the command was called in."""
    num = bot.guild_raid_counters.get(interaction.guild.id)
    # try:
    #     count = await bot.database.fetchrow(GET_RAID_COUNT_STATEMENT,
    #                                         int(ctx.guild.id))
    # except asyncpg.Exception as error:
    #     print("[!] Error obtaining raid count for guild. [{}]".format(error))
    #     return

    #num = count.get("raid_counter")
    if should_print:
        msg = "Total raids sent within this server [`{}`]".format(num)
        try:
            await interaction.response.send_message(msg)
        except discord.DiscordException as error:
            print("[!] Error sending raid count to channel. [{}]".format(error))
    else:
        await increment_raid_counter(interaction, bot, interaction.guild.id)
        return num

GET_RAIDS_FOR_GUILD = """
    SELECT * FROM raids WHERE (guild_id = $1);
"""
async def get_all_raids_for_guild(bot, interaction: discord.Interaction):
    """Admin command. Gets all raids for a guild and all pertaining data."""

    results = await bot.database.fetch(GET_RAIDS_FOR_GUILD, interaction.guild.id)

    if not results:
        message = "No raids currently running."
        return
    message = "RAIDS\n"
    for _, item in enumerate(results):
        message += "-----------------\n"
        for column, value in item.items():
            message += str(column) + ": " + str(value) + "\n"
    message += "-----------------\nEND"
    await interaction.channel.send(message)

GET_RAID_FOR_USER = """
 SELECT * FROM raids where (user_id = $1);
"""
async def check_if_in_raid(interaction: discord.Interaction, bot, user_id):
    """Checks if a user is already in a raid. Prevents double listing."""
    return await bot.database.fetchrow(GET_RAID_FOR_USER, int(user_id))

CHECK_IF_MESSAGE_IS_RAID = """
  SELECT * FROM raids WHERE (message_id = $1)
"""
async def message_is_raid(interaction: discord.Interaction, bot, message_id):
    result = await bot.database.fetchrow(CHECK_IF_MESSAGE_IS_RAID, int(message_id))
    if result:
        return True
    return False

# Redundant but different return type. Can probably be added to above but do not feel like reworking at the moment.
async def retrieve_raid_data_by_message_id(interaction: discord.Interaction, bot, message_id):

    result = await bot.database.fetchrow(CHECK_IF_MESSAGE_IS_RAID, int(message_id))

    return result

RAID_TABLE_REMOVE_RAID = """
DELETE FROM raids WHERE (message_id = $1)
RETURNING message_id
"""
UPDATE_PERSISTENCE_BONUS_BY_RAID_ID = """
    UPDATE trainer_data td
    SET persistence = persistence + 1
    FROM raid_application_user_map raum
    WHERE
    (raum.raid_message_id = $1 and raum.has_been_notified = FALSE and td.user_id = raum.user_id);
"""
CLEAR_APPLICANTS_FOR_RAID = """
DELETE FROM raid_application_user_map WHERE (raid_message_id = $1)
"""
async def remove_raid_from_table(bot, message_id):
    """Removes a raid from the table."""
    async with bot.database.connect() as c:
        await c.execute(RAID_TABLE_REMOVE_RAID, int(message_id))
        await c.execute(UPDATE_PERSISTENCE_BONUS_BY_RAID_ID, int(message_id))
        await c.execute(CLEAR_APPLICANTS_FOR_RAID, int(message_id))

async def delete_raid(bot, raid_id):
    raid_data = await retrieve_raid_data_by_message_id(None, bot, raid_id)
    if not raid_data:
        return
    try:
        await bot.http.delete_message(raid_data.get("channel_id"), raid_data.get("message_id"))
    except discord.DiscordException:
        return


async def handle_clear_user_from_raid(interaction: discord.Interaction, bot, user_id):
    guild = interaction.guild
    member = guild.get_member(int(user_id)) # conv to int just to make sure its not a string
    if not member:
        try:
            member = await guild.fetch_member(int(user_id))
        except discord.DiscordException as error:
            pass
    if not member:
        await interaction.followup.send("That user doesn't exist on this server.", ephemeral=True)
        return
    results = await check_if_in_raid(interaction, bot, user_id)
    if not results:
        await interaction.followup.send("That user is not in a raid.", ephemeral=True)
        return
    message_id = results.get("message_id")
    channel_id = results.get("channel_id")
    guild_id = results.get("guild_id")
    guild = bot.get_guild(guild_id)
    channel = guild.get_channel(channel_id)

    try:
        message = await channel.fetch_message(message_id)
        await message.delete()
    except discord.NotFound:

        await remove_raid_from_table(bot, message_id)

    except discord.DiscordException as error:
        print("[!] An error occurred trying to remove a user from their raid manually. [{}]".format(error))
        return
    await interaction.followup.send("User was successfully removed from raid.", ephemeral=True)

CHECK_VALID_RAID_CHANNEL = """
 SELECT * FROM valid_raid_channels where (channel_id = $1)
"""
async def check_if_valid_raid_channel(bot, channel_id):
    """Checks if the channel is registered as a valid raid channel."""
    channel_id = int(channel_id)
    if channel_id in bot.raid_channel_cache:
        return True

    results = await bot.database.fetchrow(CHECK_VALID_RAID_CHANNEL, channel_id)

    if results:
        bot.raid_channel_cache.add(channel_id)

    if not results:
        return False
    return True


async def process_raid(interaction: discord.Interaction, bot, tier, pokemon_name, weather, invite_slots):
    from handlers.raid_lobby_handler import create_raid_lobby, get_lobby_data_by_user_id, get_raid_lobby_category_by_guild_id

    # no need to remove user msgs if we're using slash commands
    # try:
    #     await interaction.message.delete()
    # except:
    #     pass
    # TODO send a interaction message if the raid channel is invalid 
    if not await check_if_valid_raid_channel(bot, interaction.channel.id):
        print(f"[i] Please enter the command in the valid raid channel")
        interaction.followup.send(f"Please enter the command in the correct raid channel")
        return

    if await check_if_in_raid(interaction, bot, interaction.user.id):
        await interaction.user.send(H.guild_member_dm(interaction.guild.name, "You are already in a raid."))
        return
    if await get_lobby_data_by_user_id(bot, interaction.user.id):
        await interaction.user.send(H.guild_member_dm(interaction.guild.name, "You currently have a lobby open. Please close your old lobby and retry."))
        return
    is_verified = discord.utils.get(interaction.user.roles, name="Verified Raid Host")
    try:
        invite_slots = int(invite_slots)
        if not is_verified and invite_slots > 5:
            embed = discord.Embed(title="Error", description="To host a raid with more than 5 users, you must be verified by the moderators of this server and given the 'Verified Raid Host' role to show you understand how to host a large party raid.")
            await bot.send_ignore_error(interaction.user, "", embed=embed)
            return
    except ValueError:
        pass

    raid_is_valid, response, suggestion = validate_and_format_message(interaction,
                                                                        tier,
                                                                        pokemon_name,
                                                                        weather,
                                                                        invite_slots)
    if raid_is_valid:
        temp = response.title
        temp = temp.replace("-Altered", "")
        temp = temp.replace("-Origin","")
        temp = temp.replace("-", " ")
        if not bot.dex.is_current_raid_boss(temp):
            embed = discord.Embed(title="Error", description=f"That pokemon ({temp}) is not currently in rotation. If you believe this is an error, please contact TheStaplergun#6920.")
            await bot.send_ignore_error(interaction.user, " ", embed=embed)
            return
        remove_after_seconds = 900
        channel_message_body = f'Raid hosted by {interaction.user.mention}\n'
        _, _, _, role_id = await REQH.check_if_request_message_exists(bot, response.title, interaction.guild.id)
        message_to_dm = "Your raid has been successfully listed.\nIt will automatically be deleted at the time given in `Time to Expire` or just 10 minutes.\nPress the trash can to remove it at any time."
        try:
            await interaction.user.send(H.guild_member_dm(interaction.guild.name, message_to_dm))
        except discord.Forbidden:
            await interaction.followup.send(interaction.user.name + ", I was unable to DM you. You must have your DMs open to coordinate raids.\nRaid will not be listed.", ephemeral=True)
            return
        request_channel_id = await REQH.get_request_channel(bot, interaction.guild.id)
        if request_channel_id:
            response.add_field(name="Want to be pinged for future raids?", value="📬 Add Role\n📪 Remove Role", inline=False)
        raid_lobby_category = await get_raid_lobby_category_by_guild_id(bot, interaction.guild.id)
        start_string = ""
        if role_id:
            role = discord.utils.get(interaction.guild.roles, id=role_id)
            start_string = f'{role.mention}'
        end_string = ""
        if raid_lobby_category:
            response.set_footer(text="📝 sign up")
        else:
            end_string = f' hosted by {interaction.user.mention}\n'
        channel_message_body = start_string + end_string
        try:
            message = await interaction.followup.send(channel_message_body, embed=response, wait=True)
        except discord.DiscordException as error:
            print(f'[*][{interaction.guild.name}][{interaction.user}] An error occurred listing a raid. [{error}]')
            return
        time_to_delete = datetime.now() + timedelta(seconds=remove_after_seconds)
        await add_raid_to_table(interaction, bot, message.id, interaction.guild.id, message.channel.id, interaction.user.id, time_to_delete)

        await message.add_reaction("🗑️")
        lobby = None
        if raid_lobby_category:
            time_to_remove_lobby = time_to_delete + timedelta(seconds=300)
            lobby = await create_raid_lobby(interaction, bot, message.id, interaction.user, time_to_remove_lobby, int(invite_slots))
            await message.add_reaction("📝")

        if request_channel_id:
            try:
                await message.add_reaction("📬")
                await message.add_reaction("📪")
            except discord.DiscordException as error:
                print(f'[!] Exception occurred during adding request enrollment reactions. [{error}]')
        if lobby:
            edited_message_content = f"{message.content}\n{lobby.mention} **<-lobby**"
            await message.edit(content=edited_message_content)
        print(f'[*][{interaction.guild}][{interaction.user.name}] Raid successfuly posted.')

        try:
            await SH.toggle_raid_sticky(bot, interaction, int(interaction.channel.id), int(interaction.guild.id))
        except discord.DiscordException as error:
            print(f'[!] Exception occurred during toggle of raid sticky. [{error}]')
    else:
        response += "---------\n"
        response += "*Here's the command you entered below. Suggestions were added. Check that it is correct and try again.*\n"
        await interaction.user.send(response)
        correction_suggestion = f"/raid {suggestion}"
        await interaction.user.send(correction_suggestion)
        print(f'[!][{interaction.guild}][{interaction.user.name}] Raid failed to post due to invalid arguments.')
