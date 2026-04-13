import discord

from handlers import helpers as H
from handlers import request_handler as REQH
from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH
from handlers import raid_lobby_management as RLM
from handlers import sticky_handler as SH

async def handle_reaction_remove_raid_with_lobby(bot, ctx, message):
    message_id = message.id
    results = await RH.check_if_in_raid(ctx, bot, ctx.user_id)
    if results and results.get("message_id") == message_id:
        message_to_send = "Your raid has been successfuly deleted."
        try:
            await message.delete()
        except discord.DiscordException:
            pass
    else:
        message_to_send = "You are not the host. You cannot delete this raid!"
    await ctx.member.send(H.guild_member_dm(bot.get_guild(ctx.guild_id).name, message_to_send))

async def handle_reaction_remove_raid_no_lobby(bot, ctx, message):
    user_id = message.mentions[0].id

    if int(user_id) != ctx.user_id:
        message_to_send = "You are not the host. You cannot delete this raid!"
    else:
        message_to_send = "Your raid has been successfuly deleted."

        await RH.remove_raid_from_table(bot, message.id)

        try:
            await message.delete()
        except discord.DiscordException:
            pass
        try:
            await SH.toggle_raid_sticky(bot, ctx, int(ctx.channel_id), int(ctx.guild_id))
        except discord.DiscordException as error:
            print("[!] An error occurred [{}]".format(error))
    await ctx.member.send(H.guild_member_dm(bot.get_guild(ctx.guild_id).name, message_to_send))

WATCHED_EMOJIS = (
    "📝",
    "📬",
    "📪",
    "🗑️",
    "⏱️",
    "❌"
)

async def raw_reaction_add_handle(ctx, bot):
    #Bot ignores itself adding emojis
    if ctx.user_id == bot.user.id:
        return

    if ctx.emoji.name not in WATCHED_EMOJIS:
        return

    raid_channel = await RH.check_if_valid_raid_channel(bot, ctx.channel_id)
    request_channel = await REQH.check_if_valid_request_channel(bot, ctx.channel_id)

    channel = await bot.retrieve_channel(int(ctx.channel_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(ctx.message_id))
    except discord.DiscordException:
        return

    if not message.author.id == bot.user.id:
        return

    if bot.categories_allowed and ctx.emoji.name == "⏱️" and channel.type == discord.ChannelType.private:
        await RLH.handle_activity_check_reaction(ctx, bot, message)
        return

    raid_lobby_category = await RLH.get_raid_lobby_category_by_guild_id(bot, ctx.guild_id)
    if ctx.message_id == raid_lobby_category.get("management_message_id"):
        print("[i] Handling user lobby management input")
        if ctx.emoji.name == "❌":
            await RLM.host_manual_remove_lobby(bot, ctx)
        if ctx.emoji.name == "⏱️":
            await RLM.extend_duration_of_lobby(bot, ctx)

    if raid_channel or request_channel:
        #await message.remove_reaction(ctx.emoji, discord.Object(ctx.user_id))#ctx.guild.get_member(ctx.user_id))
        category_exists = await RLH.get_raid_lobby_category_by_guild_id(bot, message.guild.id)
        if bot.categories_allowed and ctx.emoji.name == "📝":

            if not category_exists:
                return
            await RLH.handle_application_to_raid(bot, ctx, message, channel)
        elif ctx.emoji.name == "📬":
            await REQH.add_request_role_to_user(bot, ctx, message)
        elif ctx.emoji.name == "📪":
            await REQH.remove_request_role_from_user(bot, ctx, message)
        elif ctx.emoji.name == "🗑️":
            if not category_exists or not bot.categories_allowed:
                await handle_reaction_remove_raid_no_lobby(bot, ctx, message)
            else:
                await handle_reaction_remove_raid_with_lobby(bot, ctx, message)
