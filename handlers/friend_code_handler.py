import re
from datetime import datetime

import discord

from . import raid_handler as RH
from . import request_handler as REQH

INSERTED = 0
NO_UPDATE = 1
UPDATED = 2


NEW_FC_INSERT = """
INSERT INTO trainer_data(user_id, friend_code, last_time_recalled)
VALUES($1, $2, $3)
"""
GET_FC_BY_USER_ID = """
SELECT * FROM trainer_data WHERE (user_id = $1);
"""
UPDATE_FC_FOR_USER = """
    UPDATE trainer_data
    SET last_time_recalled = $3,
        friend_code = $2
    WHERE (user_id = $1);
"""
async def add_friend_code_to_table(bot, user_id, friend_code):
    """Add a trainers friend code to the database."""
    async with bot.database.connect() as c:

        result = await c.fetchrow(GET_TRAINER_DATA_BY_USER_ID,
                                  int(user_id))

        if result:
            record_friend_code = result.get("friend_code")
            if record_friend_code == friend_code:
                return NO_UPDATE

        await c.execute(UPDATE_FC_FOR_USER if result else NEW_FC_INSERT,
                        int(user_id),
                        str(friend_code),
                        datetime.now())

    return UPDATED if result else INSERTED

UPDATE_LAST_RECALLED_TIME = """
    UPDATE trainer_data
    SET last_time_recalled = $1
    WHERE (user_id = $2);
"""
UPDATE_LAST_RECALLED_AND_INCREMENT_HOST_COUNT = """
    UPDATE trainer_data
    SET last_time_recalled = $1,
        raids_hosted = raids_hosted + 1
    WHERE (user_id = $2);
"""
INSERT_BLANK_RECORD = """
    INSERT INTO trainer_data(last_time_recalled, user_id, raids_hosted)
    VALUES($1, $2, $3)
"""
async def get_friend_code(bot, user_id, host=False):
    async with bot.database.connect() as c:
        result = await c.fetchrow(GET_FC_BY_USER_ID,
                                  int(user_id))
        if result:
            # This is a bit strange, but it's a step I can perform a combined query all together.
            await c.execute(UPDATE_LAST_RECALLED_AND_INCREMENT_HOST_COUNT if host else UPDATE_LAST_RECALLED_TIME,
                            datetime.now(),
                            int(user_id))
        else:
            await c.execute(INSERT_BLANK_RECORD,
                            datetime.now(),
                            int(user_id),
                            1 if host else 0)
    return result.get("friend_code") if result and result.get("friend_code") else "To set your friend code, type `-setfc 1234 5678 9012` in any lobby or appropriate channel.", True if result else False

async def send_friend_code(ctx, bot):
    friend_code, _ = await get_friend_code(bot, ctx.author.id)
    message_to_send = f"{friend_code}\nFriend code for: {ctx.author.mention}"
    if len(friend_code) == 12:
        message_to_send = f"{message_to_send}\n```You can copy this message directly into the game.```"

    try:
        await ctx.send(message_to_send)
    except discord.DiscordException:
        pass

def validate_fc(args):
    joined_args = "".join(args)
    if not len(joined_args) == 12:
        return

    valid_format = re.compile(r'((\d){4} ?){3}')
    valid = re.match(valid_format, joined_args)

    if valid:
        return joined_args

async def get_args_list_from_message(message):
    content = message.content
    args = content.split(" ")

    if len(content) < 1:
        return args
    args.pop(0) #Pop the command out of the list
    return args

async def set_friend_code(ctx, bot):
    author = ctx.author
    raid_channel = await RH.check_if_valid_raid_channel(bot, ctx.message.channel.id)
    request_channel = await REQH.check_if_valid_request_channel(bot, ctx.message.channel.id)

    if raid_channel or request_channel:
        target = author
    else:
        target = ctx

    async with ctx.channel.typing():
        content = await get_args_list_from_message(ctx.message)
        fc = validate_fc(content)
        if not fc:
            new_embed = discord.Embed(title="Error", description="Invalid friend code. Valid friend code format is `1234 5678 9012` with or without spaces.")
            try:
                await target.send(embed=new_embed, delete_after=15)
            except discord.DiscordException:
                pass
            return

        result = await add_friend_code_to_table(bot, author.id, fc)
        if result == INSERTED:
            new_embed = discord.Embed(title="Notification", description="A new record has been created with your information. Recall it with `-trainer` or `-t`.")
        elif result == NO_UPDATE:
            new_embed = discord.Embed(title="Notification", description="That Friend Code matches the one in the database. No changes have been made.")
        elif result == UPDATED:
            new_embed = discord.Embed(title="Notification", description="Your Friend Code has been updated.")

        try:
            await target.send(embed=new_embed, delete_after=15)
        except discord.DiscordException:
            pass

NEW_LEVEL_INSERT = """
INSERT INTO trainer_data(user_id, level, last_time_recalled)
VALUES($1, $2, $3);
"""
UPDATE_LEVEL_FOR_USER = """
    UPDATE trainer_data
    SET last_time_recalled = $3,
        level = $2
    WHERE (user_id = $1);
"""
async def add_trainer_level_to_table(bot, user_id, level):
    """Add a trainers name to the database."""
    async with bot.database.connect() as c:
        result = await c.fetchrow(GET_TRAINER_DATA_BY_USER_ID,
                                  int(user_id))
        if result:
            record_level = result.get("level")
            if record_level == level:
                return NO_UPDATE

        await c.execute(UPDATE_LEVEL_FOR_USER if result else NEW_LEVEL_INSERT,
                        int(user_id),
                        int(level),
                        datetime.now())

    return UPDATED if result else INSERTED

async def set_trainer_level(ctx, bot, level):
    author = ctx.author
    raid_channel = await RH.check_if_valid_raid_channel(bot, ctx.message.channel.id)
    request_channel = await REQH.check_if_valid_request_channel(bot, ctx.message.channel.id)

    if raid_channel or request_channel:
        target = author
    else:
        target = ctx
    
    async with ctx.channel.typing():
        try:
            level = int(level)
        except ValueError:
            embed = discord.Embed(title="Error", description="The given level is invalid. It must be between 1 and 50.")
            await bot.send_ignore_error(target, "", embed=embed, delete_after=15)
            return
            
        if level < 1 or level > 50:
            embed = discord.Embed(title="Error", description="The given level is invalid. It must be between 1 and 50.")
            await bot.send_ignore_error(target, "", embed=embed, delete_after=15)
            return

        result = await add_trainer_level_to_table(bot, author.id, level)

        if result == INSERTED:
            new_embed = discord.Embed(title="Notification", description="A new record has been created with your information. Recall it with `-trainer` or `-t`.")
        elif result == NO_UPDATE:
            new_embed = discord.Embed(title="Notification", description="That level matches the one in the database. No changes have been made.")
        elif result == UPDATED:
            new_embed = discord.Embed(title="Notification", description="Your Trainer Level has been updated.")
        
        try:
            await target.send(embed=new_embed, delete_after=15)
        except discord.DiscordException:
            pass

NEW_NAME_INSERT = """
INSERT INTO trainer_data(user_id, name, last_time_recalled)
VALUES($1, $2, $3);
"""
GET_TRAINER_DATA_BY_USER_ID = """
SELECT * FROM trainer_data WHERE (user_id = $1);
"""
UPDATE_NAME_FOR_USER = """
    UPDATE trainer_data
    SET last_time_recalled = $3,
        name = $2
    WHERE (user_id = $1);
"""
async def add_trainer_name_to_table(bot, user_id, trainer_name):
    """Add a trainers name to the database."""
    async with bot.database.connect() as c:
        result = await c.fetchrow(GET_TRAINER_DATA_BY_USER_ID,
                                  int(user_id))
        if result:
            record_name = result.get("name")
            if record_name == trainer_name:
                return NO_UPDATE

        await c.execute(UPDATE_NAME_FOR_USER if result else NEW_NAME_INSERT,
                        int(user_id),
                        str(trainer_name),
                        datetime.now())

    return UPDATED if result else INSERTED

SPECIAL_CHARACTERS = "!@#$%^&*()[]{};:,./<>?\|`~-=_+\"\'"

async def set_trainer_name(ctx, bot, name):
    author = ctx.author
    raid_channel = await RH.check_if_valid_raid_channel(bot, ctx.message.channel.id)
    request_channel = await REQH.check_if_valid_request_channel(bot, ctx.message.channel.id)

    if raid_channel or request_channel:
        target = author
    else:
        target = ctx
    
    async with ctx.channel.typing():
        if any(c in SPECIAL_CHARACTERS for c in name):
            new_embed = discord.Embed(title="Error", description="A name cannot contain any special characters.")
            try:
                await target.send(embed=new_embed, delete_after=15)
            except discord.DiscordException:
                pass
            return

        if len(name) < 4 or len(name) > 15:
            new_embed = discord.Embed(title="Error", description="The length of that name is invalid. It must be between 4 and 15 characters.")
            try:
                await target.send(embed=new_embed, delete_after=15)
            except discord.DiscordException:
                pass
            return
        

        result = await add_trainer_name_to_table(bot, author.id, name)

        if result == INSERTED:
            new_embed = discord.Embed(title="Notification", description="A new record has been created with your information. Recall it with `-trainer` or `-t`.")
        elif result == NO_UPDATE:
            new_embed = discord.Embed(title="Notification", description="That name matches the one in the database. No changes have been made.")
        elif result == UPDATED:
            new_embed = discord.Embed(title="Notification", description="Your Trainer Name has been updated.")
        
        try:
            await target.send(embed=new_embed, delete_after=15)
        except discord.DiscordException:
            pass

async def send_trainer_information(ctx, bot, user_id):
    author = ctx.author
    print(user_id)
    if user_id == "0":
        user_id = ctx.author.id
    else:
        try:
            user_id = int(user_id)
        except ValueError:
            embed = discord.Embed(title="Error", description="The provided user ID is not a valid number type")
            await bot.send_ignore_error(ctx, "", embed=embed)
            return

    raid_channel = await RH.check_if_valid_raid_channel(bot, ctx.message.channel.id)
    request_channel = await REQH.check_if_valid_request_channel(bot, ctx.message.channel.id)

    if raid_channel or request_channel:
        new_embed = discord.Embed(title="Error", description="This command cannot be used here.")
        await bot.send_ignore_error(author, "", embed=new_embed)
        return

    result = await bot.database.fetchrow(GET_TRAINER_DATA_BY_USER_ID,
                                         int(user_id))

    new_embed = discord.Embed(title="Trainer Information")
    name=None
    level=None
    fc=None
    rh=0
    rp=0
    if result:
        name = result.get("name")
        level = result.get("level")
        fc = result.get("friend_code")
        rh = result.get("raids_hosted")
        rp = result.get("raids_participated_in")
        new_embed.add_field(name="Name", value=name if name else "To set your trainer name, use `-sn ANameOrSomething` or `-setname ANameOrSomething`.", inline=False)
        new_embed.add_field(name="Level", value=level if level else "To set your trainer level, use `-sl 39` or `-setlevel 39`.", inline=False)
        new_embed.add_field(name="Friend Code", value=fc if fc else "To set your trainer friend code, use `-sf` or `-setfc`.", inline=False)
        new_embed.add_field(name="Raids Hosted", value=rh, inline=True)
        new_embed.add_field(name="Raids Participated In", value=rp, inline=True)
    else:
        new_embed = discord.Embed(title="Error", description="No trainer data found for that user ID")

    await bot.send_ignore_error(ctx, "", embed=new_embed)
