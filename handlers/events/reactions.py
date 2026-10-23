import discord

from handlers import helpers as H
from handlers import request_handler as REQH
from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH
from handlers import raid_lobby_management as RLM

async def handle_reaction_remove_raid(bot, payload, message):
    raid = await RH.retrieve_raid_data_by_message_id(None, bot, message.id)
    if not raid:
        return

    user = payload.member or bot.get_user(payload.user_id) or await bot.fetch_user(payload.user_id)
    guild = bot.get_guild(payload.guild_id)
    guild_name = guild.name if guild else ""
    if int(raid.get("user_id")) != int(payload.user_id):
        if user:
            await user.send(H.guild_member_dm(guild_name, "You are not the host. You cannot delete this raid!"))
        return

    try:
        await message.delete()
    except discord.DiscordException:
        pass
    if user:
        await user.send(H.guild_member_dm(guild_name, "Your raid has been successfuly deleted."))

WATCHED_EMOJIS = (
    "📝",
    "📬",
    "📪",
    "🗑️",
    "⏱️",
    "❌"
)

async def raw_reaction_add_handle(payload, bot):
    #Bot ignores itself adding emojis
    if payload.user_id == bot.user.id:
        return

    if payload.emoji.name not in WATCHED_EMOJIS:
        return

    raid_channel = await RH.check_if_valid_raid_channel(bot, payload.channel_id)
    request_channel = await REQH.check_if_valid_request_channel(bot, payload.channel_id)

    channel = await bot.retrieve_channel(int(payload.channel_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(payload.message_id))
    except discord.DiscordException:
        return

    if not message.author.id == bot.user.id:
        return

    user = payload.member or bot.get_user(payload.user_id) or await bot.fetch_user(payload.user_id)
    if not user:
        return

    if bot.categories_allowed and payload.emoji.name == "⏱️" and channel.type == discord.ChannelType.private:
        await RLH.handle_activity_check_reaction(user, bot, message)
        return

    raid_lobby_category = await RLH.get_raid_lobby_category_by_guild_id(bot, payload.guild_id)
    if raid_lobby_category and payload.message_id == raid_lobby_category.get("management_message_id"):
        print("[i] Handling user lobby management input")
        if payload.emoji.name == "❌":
            await RLM.host_manual_remove_lobby(bot, user)
        if payload.emoji.name == "⏱️":
            await RLM.extend_duration_of_lobby(bot, user)

    if raid_channel or request_channel:
        #await message.remove_reaction(payload.emoji, discord.Object(payload.user_id))
        category_exists = await RLH.get_raid_lobby_category_by_guild_id(bot, message.guild.id)
        if bot.categories_allowed and payload.emoji.name == "📝":

            if not category_exists:
                return
            await RLH.handle_application_to_raid(bot, payload, message, channel)
        elif payload.emoji.name == "📬":
            await REQH.add_request_role_to_user(bot, payload, message)
        elif payload.emoji.name == "📪":
            await REQH.remove_request_role_from_user(bot, payload, message)
        elif payload.emoji.name == "🗑️":
            await handle_reaction_remove_raid(bot, payload, message)
