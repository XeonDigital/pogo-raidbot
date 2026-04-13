import discord

from handlers import helpers as H
from handlers import request_handler as REQH
from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH
from handlers import raid_lobby_management as RLM
from handlers import sticky_handler as SH

async def raid_delete_handle(ctx, bot):
    if not await RH.message_is_raid(ctx, bot, ctx.message_id):
        return

    await RH.remove_raid_from_table(bot, ctx.message_id)

    lobby_data = await RLH.get_lobby_data_by_raid_id(bot, ctx.message_id)
    if not lobby_data:
        return
    user_id = lobby_data.get("host_user_id")
    ctx.user_id = user_id
    raid_id = lobby_data.get("raid_message_id")
    await RLH.alter_deletion_time_for_raid_lobby(bot, raid_id)

    try:
        await SH.toggle_raid_sticky(bot, ctx, int(ctx.channel_id), int(ctx.guild_id))
    except discord.DiscordException as error:
        print("[!] An error occurred [{}]".format(error))

async def request_delete_handle(ctx, bot):
    does_exist, channel_id, message_id, role_id = await REQH.get_request_by_message_id(bot, ctx.message_id)
    guild = bot.get_guild(ctx.guild_id)
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
    await REQH.delete_request_role_and_post(ctx, bot, guild, message, role)

async def raw_message_delete_handle(ctx, bot):
    if await RH.check_if_valid_raid_channel(bot, ctx.channel_id):
        await raid_delete_handle(ctx, bot)

    if await REQH.check_if_valid_request_channel(bot, ctx.channel_id):
        await request_delete_handle(ctx, bot)

    channel_id = ctx.channel_id
    channel = bot.get_channel(int(channel_id))
    if bot.categories_allowed and channel.type == discord.ChannelType.private:
        applicant_data = await RLH.get_applicant_data_by_message_id(bot, ctx.message_id)
        if not applicant_data:
            return
        if not applicant_data.get("checked_in") and ctx.message_id == applicant_data.get("activity_check_message_id"):
            await RLH.handle_user_failed_checkin(bot, applicant_data)

async def on_guild_channel_delete(channel, bot):
    lobby_data = await RLH.get_lobby_data_by_lobby_id(bot, channel.id)
    if lobby_data:
        await RLH.remove_lobby_by_lobby_id(bot, lobby_data)
        return

    await RLH.check_if_log_channel_and_purge_data(bot, channel.id)
