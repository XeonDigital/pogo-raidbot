from datetime import datetime, timedelta
import math

import discord

from handlers import raid_handler as RH
from handlers import raid_lobby_handler as RLH

async def notify_lobby_members_of_host_deleting_lobby(lobby):
    members = lobby.members
    guild = lobby.guild
    lobby_member_role = discord.utils.get(guild.roles, name="Lobby Member")
    if not lobby_member_role:
        RLH.recreate_lobby_member_role(guild.roles)
        return

    new_embed = discord.Embed(title="Notification", description="The host has flagged the lobby for removal. It will be closed shortly.")
    for member in members:
        if lobby_member_role in member.roles:
            try:
                await member.send(embed=new_embed)
            except discord.DiscordException:
                pass

async def notify_user_cannot_alter_lobby_while_in_raid(bot, user_id):
    user = await bot.retrieve_user(user_id)
    embed = discord.Embed(title="Error", description="You cannot modify your lobby while the raid listing still exists. Please remove the listing and try again.")
    await bot.send_ignore_error(user, "", embed=embed)


async def extend_duration_of_lobby(bot, ctx):
    lobby_data = await RLH.get_lobby_data_by_user_id(bot, ctx.user_id)
    if not lobby_data:
        return
    
    raid_data = await RH.check_if_in_raid(None, bot, ctx.user_id)
    if raid_data and raid_data.get("message_id") == lobby_data.get("raid_message_id"):
        await notify_user_cannot_alter_lobby_while_in_raid(bot, ctx.user_id)
        return
        
    lobby_delete_time = lobby_data.get("delete_at")
    extension_amount = 10
    extension_measurement = "minute"
    new_delete_time = lobby_delete_time + timedelta(minutes=extension_amount)
    old_total_duration = lobby_delete_time - lobby_data.get("posted_at")
    new_total_duration = new_delete_time - lobby_data.get("posted_at")

    try:
        lobby = await bot.retrieve_channel(lobby_data.get("lobby_channel_id"))
    except discord.DiscordException:
        pass

    if not lobby:
        await RLH.remove_lobby_by_lobby_id(bot, lobby_data.get("lobby_channel_id"))
        return

    max_remaining_extendable_time = 2700 - old_total_duration.total_seconds()
    max_remaining_extendable_time_type = "minute"

    if new_total_duration.total_seconds() > 2700:
        new_time_extension = max_remaining_extendable_time
        new_delete_time = lobby_delete_time + timedelta(seconds=new_time_extension)

        if new_time_extension < 1:
            embed = discord.Embed(title="Error", description="The total lobby duration cannot be extended beyond 45 minutes.")
            await lobby.send(embed=embed)
            return
            
        if new_time_extension < 60:
            extension_amount = new_time_extension
            extension_measurement = "second"

        elif new_time_extension > 60:
            extension_amount = math.trunc(new_time_extension / 60)

    if extension_amount != 1:
        extension_measurement = f"{extension_measurement}s"

    if max_remaining_extendable_time < 60:
        max_remaining_extendable_time_type = "second"
    elif max_remaining_extendable_time >= 60:
        max_remaining_extendable_time = math.trunc(max_remaining_extendable_time / 60)
    if max_remaining_extendable_time > 1:
        max_remaining_extendable_time_type = f"{max_remaining_extendable_time_type}s"

    time_until_expiration_as_minutes = math.ceil((new_delete_time - datetime.now()).total_seconds()/60)
    new_embed = discord.Embed(title="System Notification", description=f"The host has extended the lobby duration by {extension_amount} {extension_measurement}. It will now expire in {time_until_expiration_as_minutes} minutes.\n\nYou can add up to {max_remaining_extendable_time} more {max_remaining_extendable_time_type}")
    await RLH.update_delete_time_with_given_time(bot, new_delete_time, lobby_data.get("raid_message_id"))
    await lobby.send(embed=new_embed)

async def host_manual_remove_lobby(bot, ctx):
    lobby_data = await RLH.get_lobby_data_by_user_id(bot, ctx.user_id)
    if not lobby_data:
        if ctx.author:
            new_embed = discord.Embed(title="Error", description="You are not hosting a lobby.")
            await bot.send_ignore_error(ctx.author, "", embed=new_embed)
        return

    raid_data = await RH.check_if_in_raid(None, bot, ctx.user_id)
    if raid_data and raid_data.get("message_id") == lobby_data.get("raid_message_id"):
        await notify_user_cannot_alter_lobby_while_in_raid(bot, ctx.user_id)
        return
        
    lobby = await bot.retrieve_channel(lobby_data.get("lobby_channel_id"))

    await RLH.delete_lobby(bot, lobby)

INSERT_MANAGEMENT_DATA = """
    UPDATE raid_lobby_category
    SET management_channel_id = $1,
        management_message_id = $2
    WHERE (guild_id = $3);
"""
async def insert_management_channel_data(bot, management_channel_id, management_message_id, guild_id):
    await bot.database.execute(INSERT_MANAGEMENT_DATA,
                               int(management_channel_id),
                               int(management_message_id),
                               int(guild_id))

async def create_dashboard_message(channel):
    new_embed = discord.Embed(title="Lobby Control Dashboard", description="Click one of the reactions below to control your lobby.")
    control_message = "\n".join([f"{x} {y}" for x, y in controls.items()])
    new_embed.add_field(name="Options", value=control_message, inline=False)
    try:
        message = await channel.send(embed=new_embed)
    except discord.DiscordException:
        return

    for react, name in controls.items():
        await message.add_reaction(react)
    #await message.add_reaction("⏱️")
    #await message.add_reaction("❌")

    return message

controls = {
    "⏱️":"Add 10 Minutes",
    "❌":"Close Lobby"
}
async def set_up_management_channel(ctx, bot, should_create_channel):
    channel = ctx.channel
    category_id = channel.category_id
    lobby_category_data = await RLH.get_raid_lobby_category_by_guild_id(bot, ctx.guild.id)

    raid_host_role = discord.utils.get(ctx.guild.roles, name="Raid Host")
    if not raid_host_role:
        raid_host_role = await RLH.create_raid_host_role(ctx.guild)
    overwrites = {
        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        raid_host_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
    }

    if should_create_channel and lobby_category_data and category_id == lobby_category_data.get("category_id"):
        channel = await ctx.channel.category.create_text_channel(name="lobby-management", overwrites=overwrites)
    else:
        await channel.set_permissions(raid_host_role, read_messages=True, send_messages=False)

    if not category_id:
        embed = discord.Embed(title="Error", description="This channel is not in a lobby category. A category is necessary to set up a raid lobby system. Create a category and place a channel in there, then run this command again.", color=0xff8c00)
        await ctx.send(" ",embed=embed)
        return False

    dashboard_message = await create_dashboard_message(channel)
    if not dashboard_message:
        return

    old_management_message_id = lobby_category_data.get("management_message_id")

    if old_management_message_id:
        await remove_old_message(bot, lobby_category_data)
    
    if old_management_message_id != dashboard_message.id:
        await update_message_database_info(bot, dashboard_message.id, lobby_category_data.get("guild_id"))
    
    old_management_channel_id = lobby_category_data.get("management_channel_id")
    if old_management_channel_id and old_management_channel_id != channel.id:
        await remove_old_channel(bot, lobby_category_data.get("management_channel_id"))

    await update_channel_database_info(bot, channel.id, lobby_category_data.get("guild_id"))

    #await insert_management_channel_data(bot, dashboard_message.id, channel.id)

async def remove_old_channel(bot, channel_id):
    channel_to_remove = await bot.retrieve_channel(channel_id)
    if not channel_to_remove:
        return

    await bot.delete_ignore_error(channel_to_remove)

UPDATE_MANAGEMENT_CHANNEL_ID = """
    UPDATE raid_lobby_category
    SET management_channel_id = $1
    WHERE (guild_id = $2);
"""
async def update_channel_database_info(bot, channel_id, guild_id):
    await bot.database.execute(UPDATE_MANAGEMENT_CHANNEL_ID,
                               int(channel_id),
                               int(guild_id))

UPDATE_MANAGEMENT_MESSAGE_ID = """
    UPDATE raid_lobby_category
    SET management_message_id = $1
    WHERE (guild_id = $2);
"""
async def update_message_database_info(bot, message_id, guild_id):
    await bot.database.execute(UPDATE_MANAGEMENT_MESSAGE_ID,
                               int(message_id),
                               int(guild_id))

async def remove_old_message(bot, lobby_category_data):
    management_channel_id = lobby_category_data.get("management_channel_id")
    management_message_id = lobby_category_data.get("management_message_id")

    try:
        await bot.http.delete_message(management_channel_id, management_message_id)
    except discord.DiscordException:
        pass
