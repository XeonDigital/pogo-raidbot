"""Request handler system."""
import re
import discord
import asyncpg
import handlers.helpers as H
from pogo_raid_lib import build_image_link_github, validate_pokemon

check_valid_request_channel = """
 SELECT * FROM valid_request_channels where (channel_id = $1)
"""

async def check_if_valid_request_channel(bot, channel_id):
    channel_id = int(channel_id)
    if channel_id in bot.request_channel_cache:
        return True

    results = await bot.database.fetchrow(check_valid_request_channel, channel_id)

    if results:
        bot.request_channel_cache.add(channel_id)

    if not results:
        return False
    return True

GET_ALL_REQUESTS_FOR_GUILD = """
  SELECT * FROM request_role_id_map WHERE (guild_id = $1);
"""
async def handle_get_all_requests(ctx, bot):
    results = await bot.database.fetch(GET_ALL_REQUESTS_FOR_GUILD, int(ctx.guild.id))
    await ctx.send(results)

FETCH_REQUEST_CHANNEL_INFO = """
 SELECT * FROM valid_request_channels where (guild_id = $1);
"""
async def get_request_channel(bot, guild_id):
    results = await bot.database.fetchrow(FETCH_REQUEST_CHANNEL_INFO, guild_id)
    if not results:
        return False
    return results.get("channel_id")

add_request_channel = """
INSERT INTO valid_request_channels (channel_id, guild_id)
VALUES ($1, $2)
"""
UPDATE_REQUEST_CHANNEL = """
UPDATE valid_request_channels
SET channel_id = $1
WHERE (guild_id = $2);
"""
async def database_register_request_channel(bot, ctx, channel_id, guild_id):
    request_channel_id = await get_request_channel(bot, guild_id)
    if request_channel_id:
        await handle_clear_all_requests_for_guild(ctx, bot)
    results = None

    try:
        if request_channel_id:
              await bot.database.execute(UPDATE_REQUEST_CHANNEL, int(channel_id), int(guild_id))
        else:
              results = await bot.database.execute(add_request_channel,
                                                   int(channel_id),
                                                   int(guild_id))
    except asyncpg.PostgresError as e:
        print("[!] Error occured registering request channel. [{}]".format(e))
    if results:
        print("[*] [{}] [{}] New request channel registered.".format(ctx.guild.name, channel_id))

how_to_request = """
To make a request, type the following:
`-request POKEMON_NAME`
If the pokemon is a mega pokemon, type:
`-request Mega POKEMON_NAME`
"""
def format_request_failed_dm(guild_name, wrapped_message):
    return H.guild_member_dm(guild_name, how_to_request + wrapped_message)

GET_REQUEST_POKEMON_MESSAGE = """
 SELECT * FROM request_role_id_map WHERE (role_name = $1 AND guild_id = $2);
"""
async def check_if_request_message_exists(bot, pokemon_name, guild_id):
    result = await bot.database.fetchrow(GET_REQUEST_POKEMON_MESSAGE, pokemon_name, int(guild_id))
    if not result:
        return False, None, None, None
    return True, result.get("channel_id"), result.get("message_id"), result.get("role_id")

GET_REQUEST_BY_MESSAGE_ID = """
  SELECT * FROM request_role_id_map WHERE (message_id = $1);
"""
async def get_request_by_message_id(bot, message_id):
    result = await bot.database.fetchrow(GET_REQUEST_BY_MESSAGE_ID, int(message_id))
    if not result:
        return False, None, None, None
    return True, result.get("channel_id"), result.get("message_id"), result.get("role_id")

INSERT_NEW_ROLE = """
INSERT INTO request_role_id_map (role_id, message_id, guild_id, role_name)
VALUES ($1, $2, $3, $4);
"""
async def set_up_request_role_and_message(bot, ctx, pokemon_name, number):
    guild = ctx.guild
    try:
        new_role = await guild.create_role(name=pokemon_name, reason="Setting up a request role.")
    except discord.DiscordException as error:
        print("[!] An error occurred creating a new role: [{}]".format(error))
    author = ctx.author
    try:
        await give_request_role(author, guild, new_role)
    except discord.DiscordException as error:
        print("[!] An error occurred giving a user a role: [{}]".format(error))
        return
    new_embed = discord.Embed(title=pokemon_name.title(), description="")
    new_embed.set_thumbnail(url=build_image_link_github(number))
    new_embed.add_field(name="Number of players requesting", value=str(1))
    new_embed.add_field(name="Want to be pinged for raids?", value="📬 Add Role\n📪 Remove Role", inline=False)

    request_channel_id = await get_request_channel(bot, guild.id)
    request_channel = guild.get_channel(request_channel_id)
    try:
        message = await request_channel.send(embed=new_embed)
    except discord.DiscordException as error:
        print("[!] An error occurred setting up the request sticky message. [{}]".format(error))
        #await author.remove_roles([new_role])
        return
    try:
        await message.add_reaction("📬")
        await message.add_reaction("📪")
    except discord.DiscordException as error:
        print("[!][{}] An error occurred while adding reactions to a new request listing. [{}]".format(error))

    try:
        await bot.database.execute(INSERT_NEW_ROLE, new_role.id, message.id, guild.id, pokemon_name)
    except asyncpg.PostgresError as error:
        #await message.delete()
        #await author.remove_roles([new_role])
        print("[!] An error occurred inserting the new role data. [{}]".format(error))

GET_ALL_ROLES_FOR_GUILD = """
  SELECT * FROM request_role_id_map
  WHERE (guild_id = $1);
"""
DELETE_ALL_ROLE_DATA_FOR_GUILD = """
  DELETE FROM request_role_id_map
  WHERE (guild_id = $1)
"""
async def handle_clear_all_requests_for_guild(ctx, bot):
    if not ctx.message.channel.permissions_for(ctx.author).manage_roles or\
       not ctx.message.channel.permissions_for(ctx.author).manage_messages:
        embed = discord.Embed(title="", description="You do not have permission to manage channels in the target guild.")
        await bot.send_ignore_error(ctx, "", embed=embed, delete_after=15)
        return False

    async with bot.database.connect() as c:
        query_results = await c.fetch(GET_ALL_ROLES_FOR_GUILD, ctx.guild.id)
        await c.execute(DELETE_ALL_ROLE_DATA_FOR_GUILD, ctx.guild.id)

    guild = ctx.guild
    channel_id = await get_request_channel(bot, guild.id)
    channel = guild.get_channel(channel_id)
    for result in query_results:
        role_id = result.get("role_id")
        message_id = result.get("message_id")
        role = discord.utils.get(guild.roles, id=role_id)
        try:
            if role:
                await role.delete()
        except discord.DiscordException as error:
            print("[!] An error occurred deleting a role. [{}]".format(error))
        try:
            await channel.delete_messages([discord.Object(message_id)])
        except discord.NotFound:
            pass
        except discord.DiscordException as error:
            print("[!][{}] An error occurred when deleting a message [{}]".format(guild.name,  error))
    await ctx.send("Total roles deleted: [{}]".format(len(query_results)), delete_after=15)

async def give_request_role(author, guild, role):
    blurb = "You have been given the role {} and you will be pinged **every time** a raid with that Pokémon name is created. If you want to opt out of the listings for this Pokémon, click on the 📪 on the listing in the requests channel. To opt back in, click on the 📬.".format(role.name)
    dm_message = H.guild_member_dm(guild.name, blurb)
    try:
        await author.add_roles(role, reason="Giving user a request role.")
        await author.send(dm_message)
    except discord.DiscordException as error:
        print("[!] An error occurred giving a user a role: [{}]".format(error))
        return

async def increment_request_count(ctx, bot, channel_id, message_id):
    guild = ctx.guild
    request_channel_id = await get_request_channel(bot, guild.id)
    request_channel = guild.get_channel(request_channel_id)
    try:
        message = await request_channel.fetch_message(message_id)
    except discord.DiscordException as error:
        return
    if len(message.embeds) == 1:
        embed = message.embeds[0]
        old_field = embed.fields[0]
        count = int(old_field.value)
    else:
        return

    count += 1
    new_embed = discord.Embed(title=embed.title, description="")
    thumbnail_url = embed.thumbnail.url
    if re.search(r'_shiny', thumbnail_url):
        thumbnail_url = thumbnail_url.replace("_shiny","")
    #if not re.search(r'_shiny', thumbnail_url):
    #    if re.search(r'shiny', thumbnail_url):
    #        thumbnail_url = thumbnail_url.replace("shiny", "_shiny")
    #    else:
    #        thumbnail_url = thumbnail_url[:len(thumbnail_url) - 4] + "_shiny" + thumbnail_url[len(thumbnail_url) - 4:]
    new_embed.set_thumbnail(url=thumbnail_url)
    new_embed.add_field(name=old_field.name, value=str(count))
    new_embed.add_field(name="Want to be pinged for raids?", value="📬 Add Role\n📪 Remove Role", inline=False)
    try:
        await message.edit(embed=new_embed)
    except discord.DiscordException as error:
        print("[!] An error occurred trying to update a request tracker. [{}]".format(error))

async def decrement_request_count(ctx, bot, channel_id, message_id):
    guild = ctx.guild
    request_channel_id = await get_request_channel(bot, guild.id)
    request_channel = guild.get_channel(request_channel_id)
    try:
        message = await request_channel.fetch_message(message_id)
    except discord.DiscordException:
        return

    if len(message.embeds) == 1:
        embed = message.embeds[0]
        old_field = embed.fields[0]
        count = int(old_field.value)
    else:
        return

    count -= 1
    if count <= 0:
        role = discord.utils.get(guild.roles, name=embed.title)
        await delete_request_role_and_post(ctx, bot, guild, message, role)
        return
    new_embed = discord.Embed(title=embed.title, description="")
    thumbnail_url = embed.thumbnail.url
    if re.search(r'_shiny', thumbnail_url):
        thumbnail_url = thumbnail_url.replace("_shiny","")
    #if not re.search(r'_shiny', thumbnail_url):
    #    if re.search(r'shiny', thumbnail_url):
    #        thumbnail_url = thumbnail_url.replace("shiny", "_shiny")
    #    else:
    #        thumbnail_url = thumbnail_url[:len(thumbnail_url) - 4] + "_shiny" + thumbnail_url[len(thumbnail_url) - 4:]
    new_embed.set_thumbnail(url=thumbnail_url)
    new_embed.add_field(name=old_field.name, value=str(count))
    new_embed.add_field(name="Want to be pinged for raids?", value="📬 Add Role\n📪 Remove Role", inline=False)
    try:
        await message.edit(embed=new_embed)
    except discord.DiscordException as error:
        print("[!] An error occurred trying to update a request tracker. [{}]".format(error))

DELETE_REQUEST_FROM_TABLE = """
    DELETE FROM request_role_id_map WHERE (role_id = $1)
    RETURNING message_id
"""
async def delete_request_role_and_post(ctx, bot, guild, message, role):
    try:
        if message:
            await message.delete()
    except:
        pass
    role_id = role.id
    try:
        await role.delete(reason="No users requesting this pokemon any more")
    except discord.DiscordException as error:
        print("[!][{}] An exception occurred attempting to delete a role. [{}]".format(guild.name, error))

    try:
        await bot.database.execute(DELETE_REQUEST_FROM_TABLE, role_id)
    except asyncpg.PostgresError as error:
        print("[!] An exception occurred attempting to remove a role listing from the database. [{}]".format(error))

async def check_if_user_already_assigned_role(member, role_id):
    if discord.utils.get(member.roles, id=role_id):
        return True
    return False

async def request_pokemon_handle(bot, ctx, tier, pokemon_name):
    """Sets up a request and gives you a role for that Pokemon"""
    author = ctx.author
    if not tier or (tier.lower() == "mega" and not pokemon_name):
        await author.send(format_request_failed_dm(ctx.guild.name, "No pokemon given to request."))
        return
    channel_id = ctx.channel.id

    if not pokemon_name:
        pokemon_name = tier
        tier = ""
    guild_id = ctx.guild.id
    is_valid, response, suggestion, dex_num = validate_pokemon(pokemon_name, tier)
    if tier.lower() == "mega" and not pokemon_name.startswith("Mega ", 0, 5):
        pokemon_name = "Mega " + pokemon_name
    if not is_valid:
        author_dm = H.guild_member_dm(ctx.guild.name, "")
        author_dm += response
        author_dm += "---------\n"
        author_dm += "*Here's the command you entered below. Suggestions were added. Check that it is correct and try again.*\n"
        try:
            await author.send(author_dm)
        except discord.Forbidden:
            return
        correction_suggestion = ctx.prefix + "request " + suggestion
        await ctx.author.send(correction_suggestion)
    else:
        pokemon_name = pokemon_name.title()
        temp = pokemon_name.replace("-Altered", "")
        temp = temp.replace("-Origin","")
        if temp.replace("-", " ") not in bot.dex.current_raid_bosses():
            embed = discord.Embed(title="Error", description=f"That pokemon ({pokemon_name}) is not currently in rotation. If you believe this is an error, please contact TheStaplergun#6920.")
            await bot.send_ignore_error(ctx.author, " ", embed=embed)
            return
        does_exist, request_channel_id, message_id, role_id = await check_if_request_message_exists(bot, pokemon_name, guild_id)
        if not does_exist:
            await set_up_request_role_and_message(bot, ctx, pokemon_name, dex_num)
            return

        if not await check_if_user_already_assigned_role(author, role_id):
            role = discord.utils .get(ctx.guild.roles, id=role_id)
            await give_request_role(author, ctx.guild, role)
            await increment_request_count(ctx, bot, request_channel_id, message_id)
    return

async def remove_request_pokemon_handle(bot, ctx, tier, pokemon_name):
    author = ctx.author
    if tier.lower() == "mega" and not pokemon_name.startswith("Mega", 0, 5):
        pokemon_name = "Mega " + pokemon_name
    if not discord.utils.get(author.roles, name=pokemon_name):
        return
    _, request_channel_id, message_id, role_id = await check_if_request_message_exists(bot, pokemon_name, ctx.guild.id)
    #if not discord.utils.get(author.roles, id=role_id):
    #    return
    try:
        await author.remove_roles(discord.Object(role_id))
    except discord.DiscordException as error:
        print("[!][{}] An error occurred removing a role from a user. [{}]".format(ctx.guild.name, error))
    await decrement_request_count(ctx, bot, request_channel_id, message_id)


async def add_request_role_to_user(bot, ctx, message):
    is_mega, pokemon_name = H.get_pokemon_name_from_raid(message)

    ctx.guild = bot.get_guild(ctx.guild_id)
    ctx.channel = ctx.guild.get_channel(ctx.channel_id)
    ctx.author = ctx.guild.get_member(ctx.user_id)
    if not ctx.author:
        try:
            ctx.author = ctx.guild.fetch_member(ctx.user_id)
        except discord.DiscordException as error:
            print("[!] An error occurred fetching a member from the guild [{}]".format(ctx.guild))

    tier = pokemon_name
    if is_mega:
        tier = "Mega"

    await request_pokemon_handle(bot, ctx, tier, pokemon_name)

async def remove_request_role_from_user(bot, ctx, message):
    is_mega, pokemon_name = H.get_pokemon_name_from_raid(message)

    ctx.guild = bot.get_guild(ctx.guild_id)
    ctx.channel = ctx.guild.get_channel(ctx.channel_id)
    ctx.author = ctx.guild.get_member(ctx.user_id)
    if not ctx.author:
        try:
            ctx.author = ctx.guild.fetch_member(ctx.user_id)
        except discord.DiscordException as error:
            print("[!] An error occurred fetching a member from the guild [{}]".format(ctx.guild))

    tier = pokemon_name
    if is_mega:
        tier = "Mega"

    await remove_request_pokemon_handle(bot, ctx, tier, pokemon_name)
