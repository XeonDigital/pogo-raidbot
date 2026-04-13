"""Sticky message handler"""
import discord

from . import raid_handler as RH
#import handlers.raid_handler as RH

CHECK_FOR_RAIDS_IN_GUILD_CHANNEL = """
 SELECT * FROM raids where (channel_id = $1);
"""
async def check_if_raids_remaining_in_channel(bot, channel_id):
    results = await bot.database.fetchrow(CHECK_FOR_RAIDS_IN_GUILD_CHANNEL, int(channel_id))
    if not results:
        return False
    return True

RAID_PLACEHOLDER_STICKY_SELECT = """
 SELECT * FROM raid_placeholder_stickies where (channel_id = $1);
"""
async def get_sticky_message(bot, channel_id):
    record = await bot.database.fetchrow(RAID_PLACEHOLDER_STICKY_SELECT, int(channel_id))
    if not record:
        return (False, None)

    message_id = int(record.get("message_id"))
    channel = bot.get_channel(channel_id)
    try:
        message = await channel.fetch_message(message_id)
    except discord.NotFound as error:
        print(error)
        return (True, None)

    if not message:
        return (True, None)

    return (True, message)

ADD_PLACEHOLDER_STICKY_MESSAGE = """
INSERT INTO raid_placeholder_stickies(channel_id, message_id, guild_id)
VALUES($1, $2, $3);
"""
async def update_placeholder_database(bot, channel_id, message_id, guild_id):
    await bot.database.execute(ADD_PLACEHOLDER_STICKY_MESSAGE,
                               int(channel_id),
                               int(message_id),
                               int(guild_id))

DELETE_PLACEHOLDER_STICKY_MESSAGE = """
DELETE FROM raid_placeholder_stickies WHERE (channel_id = $1)
RETURNING channel_id;
"""
async def remove_old_sticky_message_from_table(bot, channel_id):
    results = await bot.database.execute(DELETE_PLACEHOLDER_STICKY_MESSAGE, int(channel_id))
    print("[*] Table operation results [{}]".format(results))

async def make_new_no_raids_placeholder_message(bot, channel_id):
    channel = bot.get_channel(channel_id)
    title = "No raids available."
    description = "Check back any time to see if one has been listed."
    embed = await format_sticky_embed(title, description)
    message = await channel.send(embed=embed)

    await update_placeholder_database(bot, int(channel.id), int(message.id), int(channel.guild.id))

async def make_new_raids_remaining_placeholder_message(bot, channel_id):
    channel = bot.get_channel(channel_id)
    title = "Raids available!"
    description = "All available raids are listed below."
    embed = await format_sticky_embed(title, description)
    message = await channel.send(embed=embed)

    await update_placeholder_database(bot, int(channel.id), int(message.id), int(channel.guild.id))

async def format_sticky_embed(title, description):
    embed = discord.Embed(title=title, description=description, color=0xff8c00)
    embed_host_raid_msg = "If you want to host a raid, check out the post above!"
    embed.add_field(name="Want to host a raid?", value=embed_host_raid_msg, inline=False)
    return embed

async def edit_to_no_raids_remaining_placeholder(message):
    title = "No raids available."
    description = "Check back any time to see if one has been listed."
    embed = await format_sticky_embed(title, description)
    await message.edit(embed=embed)

async def edit_to_raids_remaining_placeholder(message):
    title = "Raids available!"
    description = "All available raids are listed below."
    embed = await format_sticky_embed(title, description)
    await message.edit(embed=embed)

async def toggle_raid_sticky(bot, ctx, channel_id, guild_id):
    from handlers.raid_handler import check_if_valid_raid_channel
    if not await check_if_valid_raid_channel(bot, channel_id):
        return
    try:

        raids_remaining = await check_if_raids_remaining_in_channel(bot, channel_id)

        message_exists_in_table, message = await get_sticky_message(bot, channel_id)
        if message:
            if not raids_remaining:
                await edit_to_no_raids_remaining_placeholder(message)
                return

            await edit_to_raids_remaining_placeholder(message)
            return

        if message_exists_in_table:
            await remove_old_sticky_message_from_table(bot, channel_id)

        if not raids_remaining:
            await make_new_no_raids_placeholder_message(bot, channel_id)
            return

        await make_new_raids_remaining_placeholder_message(bot, channel_id)
        return

    except discord.DiscordException as error:
        print("[!] An exception occured while creating a placeholder. [{}]".format(error))
