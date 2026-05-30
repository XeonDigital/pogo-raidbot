import discord

from handlers import helpers as H
from handlers import request_handler as REQH
from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH

async def on_message_handle(message, bot):
    if message.author.bot:
        return True
    # Handle this first because it's a logging function.
    raid_lobby_channel_data = await RLH.get_lobby_data_by_lobby_id(bot, message.channel.id)
    raid_lobby_channel = None
    if raid_lobby_channel_data:
        raid_lobby_channel = await bot.retrieve_channel(message.channel.id)

    if bot.categories_allowed and raid_lobby_channel:
        await RLH.log_message_in_raid_lobby_channel(bot, message, raid_lobby_channel, raid_lobby_channel_data)
        return True

    raid_channel = await RH.check_if_valid_raid_channel(bot, message.channel.id)
    request_channel = await REQH.check_if_valid_request_channel(bot, message.channel.id)

    if not raid_channel and not request_channel and not raid_lobby_channel:
        return False

    #if message.author.id == bot.user.id:
        #return False

    if message.channel.permissions_for(message.author).manage_messages:
        return False
    elif raid_channel or request_channel:
        try:
            await message.delete()
        except discord.DiscordException:
            pass

    content = message.content

    await message.author.send(H.guild_member_dm(message.guild.name, "This is a curated channel. Read the guide and use the correct interaction/slash-command for this channel."))

    print("[*][{}][{}] Invalid message deleted [{}]".format(message.guild.name, message.author.name, content))
