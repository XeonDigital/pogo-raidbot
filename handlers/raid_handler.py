"""Raid listings: validate a host, post the channel embed, and track it in the database.

``process_raid`` is the ``/raid`` entry point. It checks the channel and that the
user is not already hosting, infers the boss from the current rotation (prompting
for tier when more than one match exists), then lists the raid, optionally opens a
lobby, posts counters, and updates the channel sticky. The rest of this module is
SQL helpers for inserting, looking up, and deleting those listing rows.
"""
from datetime import datetime, timedelta, timezone

import asyncpg
import discord

import handlers.helpers as H
#import handlers.raid_lobby_handler as RLH
import handlers.request_handler as REQH
import handlers.sticky_handler as SH
from handlers.pokebattler.api_helper import get_counter
from pogo_raid_lib import validate_and_format_message, validate_pokemon, validate_tier

NEW_RAID_INSERT = """
INSERT INTO raids(message_id, time_registered, guild_id, channel_id, user_id, time_to_remove)
VALUES($1, $2, $3, $4, $5, $6)
"""
async def add_raid_to_table(interaction: discord.Interaction, bot, message_id, guild_id, channel_id, user_id, time_to_remove):
    """Add a raid to the database with all the given data points."""
    cur_time = datetime.now(tz=timezone.utc)

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
            await interaction.followup.send(msg)
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


async def remove_listing_for_raid(bot, raid_message_id):
    """Remove the public listing and raid row. No-op if the listing is already gone.

    The raids row is deleted first so on_raw_message_delete does not treat this
    as a user-deleted listing and reschedule the lobby.
    """
    if not raid_message_id:
        return
    raid_data = await retrieve_raid_data_by_message_id(None, bot, raid_message_id)
    if not raid_data:
        return

    await remove_raid_from_table(bot, raid_data.get("message_id"))
    try:
        await bot.http.delete_message(int(raid_data.get("channel_id")), int(raid_data.get("message_id")))
    except discord.DiscordException as error:
        print(f"[!] Failed to delete raid listing message. [{error}]")
    try:
        await SH.toggle_raid_sticky(bot, None, int(raid_data.get("channel_id")), int(raid_data.get("guild_id")))
    except discord.DiscordException as error:
        print(f"[!] Exception occurred during toggle of raid sticky. [{error}]")


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


def optional_raid_tier(tier):
    if tier is None:
        return None
    text = str(tier).strip()
    if not text or text.lower() in ("none", "no tier provided"):
        return None
    return text


def canonical_slash_tier(tier):
    ok, response = validate_tier(tier)
    if not ok:
        return None
    return response.lower().replace("t", "")


def listing_name_for_match(pokemon_name, match):
    if match.shadow:
        return f"Shadow {match.name}"
    return match.name or pokemon_name


class RaidTierButton(discord.ui.Button):
    def __init__(self, match):
        label = "Mega" if match.slash_tier == "mega" else str(match.slash_tier)
        if match.shadow:
            label = f"{label} Shadow"
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.match = match

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        for item in view.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(view=view)
        except discord.DiscordException:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        pokemon_name = listing_name_for_match(view.pokemon_name, self.match)
        await process_raid(
            interaction,
            view.bot,
            self.match.slash_tier,
            pokemon_name,
            view.weather,
            view.invite_slots,
            True,
        )


class RaidTierPickView(discord.ui.View):
    def __init__(self, bot, pokemon_name, weather, invite_slots, matches, owner_id):
        super().__init__(timeout=120)
        self.bot = bot
        self.pokemon_name = pokemon_name
        self.weather = weather
        self.invite_slots = invite_slots
        self.owner_id = owner_id
        self.message = None
        for match in matches:
            self.add_item(RaidTierButton(match))

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message(
            "Only the person who ran this command can pick a tier.",
            ephemeral=True,
        )
        return False

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.DiscordException:
                pass


async def prompt_for_raid_tier(interaction, bot, pokemon_name, weather, invite_slots, matches):
    view = RaidTierPickView(bot, pokemon_name, weather, invite_slots, matches, interaction.user.id)
    view.message = await interaction.followup.send(
        "That Pokémon is in more than one raid tier right now. Pick which one you're hosting.",
        view=view,
        ephemeral=True,
        wait=True,
    )


async def resolve_raid_boss(interaction, bot, tier, pokemon_name, weather, invite_slots):
    """Infer slash tier from the current rotation, or ask the host to pick.

    Returns (tier, pokemon_name) when listing can continue, otherwise None.
    """
    provided_tier = optional_raid_tier(tier)
    matches = bot.dex.matching_rotation_bosses(pokemon_name)
    if provided_tier:
        canonical = canonical_slash_tier(provided_tier)
        matches = [match for match in matches if canonical and match.slash_tier == canonical]
        if not matches:
            return provided_tier, pokemon_name

    if not matches:
        is_valid, response, _, _ = validate_pokemon(pokemon_name, "5")
        if not is_valid:
            await interaction.followup.send(H.guild_member_dm(interaction.guild.name, response), ephemeral=True)
            return None
        embed = discord.Embed(
            title="Error",
            description=f"That pokemon ({pokemon_name}) is not currently in rotation. If you believe this is an error, please contact TheStaplergun#6920.",
        )
        await bot.send_ignore_error(interaction.user, " ", embed=embed)
        return None

    if len(matches) > 1:
        await prompt_for_raid_tier(interaction, bot, pokemon_name, weather, invite_slots, matches)
        return None

    match = matches[0]
    return match.slash_tier, listing_name_for_match(pokemon_name, match)


async def reject_if_cannot_host(interaction, bot, invite_slots):
    """Return invite_slots if hosting can continue, otherwise None."""
    from handlers.raid_lobby_handler import get_lobby_data_by_user_id

    if not await check_if_valid_raid_channel(bot, interaction.channel.id):
        print(f"[i] Please enter the command in the valid raid channel")
        await interaction.followup.send(f"Please enter the command in the correct raid channel")
        return None
    if await check_if_in_raid(interaction, bot, interaction.user.id):
        await interaction.followup.send(H.guild_member_dm(interaction.guild.name, "You are already in a raid."))
        return None
    if await get_lobby_data_by_user_id(bot, interaction.user.id):
        await interaction.followup.send(H.guild_member_dm(interaction.guild.name, "You currently have a lobby open. Please close your old lobby and retry."))
        return None
    is_verified = discord.utils.get(interaction.user.roles, name="Verified Raid Host")
    try:
        invite_slots = int(invite_slots)
        if not is_verified and invite_slots > 5:
            embed = discord.Embed(title="Error", description="To host a raid with more than 5 users, you must be verified by the moderators of this server and given the 'Verified Raid Host' role to show you understand how to host a large party raid.")
            await bot.send_ignore_error(interaction.user, "", embed=embed)
            return None
    except ValueError:
        pass
    return invite_slots


async def resolve_and_validate_raid(interaction, bot, tier, pokemon_name, weather, invite_slots, already_resolved):
    """Return (tier, pokemon_name, weather, embed) if the raid can be listed, otherwise None."""
    if not weather or str(weather).strip().lower() in ("no weather condition provided",):
        weather = "unknown"
    if not already_resolved:
        resolved = await resolve_raid_boss(interaction, bot, tier, pokemon_name, weather, invite_slots)
        if resolved is None:
            return None
        tier, pokemon_name = resolved
    raid_is_valid, response, suggestion = validate_and_format_message(interaction,
                                                                        tier,
                                                                        pokemon_name,
                                                                        weather,
                                                                        invite_slots)
    if not raid_is_valid:
        response += "---------\n"
        response += "*Here's the command you entered below. Suggestions were added. Check that it is correct and try again.*\n"
        correction_suggestion = f"/raid {suggestion}"
        await interaction.followup.send(response + "\n" + correction_suggestion)
        print(f'[!][{interaction.guild}][{interaction.user.name}] Raid failed to post due to invalid arguments.')
        return None
    temp = response.title
    temp = temp.replace("-Altered", "")
    temp = temp.replace("-Origin","")
    temp = temp.replace("-", " ")
    if not bot.dex.is_current_raid_boss(temp):
        embed = discord.Embed(title="Error", description=f"That pokemon ({temp}) is not currently in rotation. If you believe this is an error, please contact TheStaplergun#6920.")
        await bot.send_ignore_error(interaction.user, " ", embed=embed)
        return None
    return tier, pokemon_name, weather, response


async def publish_raid_listing(interaction, bot, tier, pokemon_name, weather, invite_slots, embed):
    from handlers.raid_lobby_handler import create_raid_lobby, get_lobby_data_by_user_id, get_raid_lobby_category_by_guild_id

    remove_after_seconds = 900
    _, _, _, role_id = await REQH.check_if_request_message_exists(bot, embed.title, interaction.guild.id)
    time_to_delete = datetime.now(tz=timezone.utc) + timedelta(seconds=remove_after_seconds)
    message_to_dm = f"Your raid has been successfully listed.\nIt will automatically be deleted in just 15 minutes or at <t:{int(time_to_delete.timestamp())}:t>.\nPress the trash can to remove it at any time."
    try:
        await interaction.user.send(H.guild_member_dm(interaction.guild.name, message_to_dm))
    except discord.Forbidden:
        await interaction.followup.send(interaction.user.name + ", I was unable to DM you. You must have your DMs open to coordinate raids.\nRaid will not be listed.", ephemeral=True)
        return
    request_channel_id = await REQH.get_request_channel(bot, interaction.guild.id)
    if request_channel_id:
        embed.add_field(name="Want to be pinged for future raids?", value="📬 Add Role\n📪 Remove Role", inline=False)
    raid_lobby_category = await get_raid_lobby_category_by_guild_id(bot, interaction.guild.id)
    start_string = ""
    if role_id:
        role = discord.utils.get(interaction.guild.roles, id=role_id)
        start_string = f'{role.mention}'
    end_string = ""
    if raid_lobby_category:
        embed.set_footer(text="📝 sign up")
    else:
        end_string = f' hosted by {interaction.user.mention}\n'
    channel_message_body = start_string + end_string
    try:
        message = await interaction.channel.send(channel_message_body, embed=embed)
        await interaction.followup.send("Raid listed in the channel.", ephemeral=True)
    except discord.DiscordException as error:
        print(f'[*][{interaction.guild.name}][{interaction.user}] An error occurred listing a raid. [{error}]')
        return
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
        try:
            from handlers.events.interactions import log_slash_command_for_lobby
            lobby_data = await get_lobby_data_by_user_id(bot, interaction.user.id)
            await log_slash_command_for_lobby(bot, interaction, lobby, lobby_data)
        except Exception as error:
            print(f"[!] Failed to log /raid command. [{error}]")
    print(f'[*][{interaction.guild}][{interaction.user.name}] Raid successfuly posted.')

    try:
        await get_counter(bot, interaction, tier, pokemon_name, weather, lobby or interaction.channel, False)
    except Exception as error:
        print(f"[!][{interaction.guild}][{interaction.user.name}] Failed to post raid counters. [{error}]")

    try:
        await SH.toggle_raid_sticky(bot, interaction, int(interaction.channel.id), int(interaction.guild.id))
    except discord.DiscordException as error:
        print(f'[!] Exception occurred during toggle of raid sticky. [{error}]')


async def process_raid(interaction: discord.Interaction, bot, tier, pokemon_name, weather, invite_slots, already_resolved=False):
    invite_slots = await reject_if_cannot_host(interaction, bot, invite_slots)
    if invite_slots is None:
        return
    resolved = await resolve_and_validate_raid(interaction, bot, tier, pokemon_name, weather, invite_slots, already_resolved)
    if resolved is None:
        return
    tier, pokemon_name, weather, embed = resolved
    await publish_raid_listing(interaction, bot, tier, pokemon_name, weather, invite_slots, embed)
