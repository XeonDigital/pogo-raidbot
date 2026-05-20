import discord

from handlers import helpers as H
from handlers import request_handler as REQH
from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH
from handlers import raid_lobby_management as RLM
from handlers import sticky_handler as SH

async def raid_delete_handle(payload, bot):
    if not await RH.message_is_raid(payload, bot, payload.message_id):
        return

    await RH.remove_raid_from_table(bot, payload.message_id)

    lobby_data = await RLH.get_lobby_data_by_raid_id(bot, payload.message_id)
    if not lobby_data:
        return
    
    # We no longer modify the payload object. Let `alter_deletion_time_for_raid_lobby`
    # handle it implicitly via the IDs stored.
    raid_id = lobby_data.get("raid_message_id")
    await RLH.alter_deletion_time_for_raid_lobby(bot, raid_id)

    try:
        # In `event_listeners.py` raw message events do not create a command interaction.
        # We pass `None` for interaction, as toggle_raid_sticky uses database lookups primarily.
        await SH.toggle_raid_sticky(bot, None, int(payload.channel_id), int(payload.guild_id))
    except discord.DiscordException as error:
        print("[!] An error occurred [{}]".format(error))

async def request_delete_handle(payload, bot):
    does_exist, channel_id, message_id, role_id = await REQH.get_request_by_message_id(bot, payload.message_id)
    guild = bot.get_guild(payload.guild_id)
    if not does_exist:
        return
    role = discord.utils.get(guild.roles, id=role_id)
    channel = guild.get_channel(channel_id)
    message = None
    try:
        if channel:
            message = await channel.fetch_message(message_id)
    except discord.DiscordException:
        pass
    
    # Passing payload instead of context
    await REQH.delete_request_role_and_post(payload, bot, guild, message, role)

async def raw_message_delete_handle(payload, bot):
    if await RH.check_if_valid_raid_channel(bot, payload.channel_id):
        await raid_delete_handle(payload, bot)

    if await REQH.check_if_valid_request_channel(bot, payload.channel_id):
        await request_delete_handle(payload, bot)

    channel_id = payload.channel_id
    channel = bot.get_channel(int(channel_id))
    
    # Need to check `channel` validity before checking `.type`
    if channel and bot.categories_allowed and channel.type == discord.ChannelType.private:
        applicant_data = await RLH.get_applicant_data_by_message_id(bot, payload.message_id)
        if not applicant_data:
            return
        if not applicant_data.get("checked_in") and payload.message_id == applicant_data.get("activity_check_message_id"):
            await RLH.handle_user_failed_checkin(bot, applicant_data)

async def on_guild_channel_delete(channel, bot):
    lobby_data = await RLH.get_lobby_data_by_lobby_id(bot, channel.id)
    if lobby_data:
        await RLH.remove_lobby_by_lobby_id(bot, lobby_data)
        return

    await RLH.check_if_log_channel_and_purge_data(bot, channel.id)
