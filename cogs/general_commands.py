"""Cog containing general commands"""
import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

import handlers.friend_code_handler as FCH
import handlers.pokebattler.api_helper as APIH
import handlers.raid_lobby_handler as RLH
import handlers.raid_lobby_management as RLM

class GeneralCommands(commands.Cog):
    """General Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="ping", description="Check if the bot is alive and latency.")
    async def ping(self, interaction: discord.Interaction):
        curr = time.time()
        latency: float = round(self.__bot.latency * 1000.0, 2)
        await interaction.response.send_message('Pinging... 🏓', ephemeral=True)
        msg = await interaction.original_response()
        await msg.edit(
            content=f'🏓 Pong! Latency is {round((time.time() - curr) * 1000.0, 2)}ms. API latency is {latency}ms.')

    @app_commands.command(name="setfc", description="Allows a user to register their Pokemon Go friend code.")
    async def setfc(self, interaction: discord.Interaction, fc: str):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_friend_code(interaction, self.__bot, fc)

    @app_commands.command(name="setname", description="Allows a user to register their Pokemon Go trainer name.")
    async def setname(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_trainer_name(interaction, self.__bot, name)

    @app_commands.command(name="setlevel", description="Allows a user to register their Pokemon Go trainer level.")
    async def setlevel(self, interaction: discord.Interaction, level: int):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_trainer_level(interaction, self.__bot, level)

    @app_commands.command(name="fc", description="Sends your registered friend code to the channel.")
    async def fc(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await FCH.send_friend_code(interaction, self.__bot)

    @app_commands.command(name="trainer", description="Look up trainer information.")
    async def trainer(self, interaction: discord.Interaction, user_id: str = "0"):
        await interaction.response.defer(ephemeral=True)
        await FCH.send_trainer_information(interaction, self.__bot, user_id)

    @app_commands.command(name="dex", description="Retrieves Pokedex information for a Pokedex number or Pokemon Name.")
    async def dex(self, interaction: discord.Interaction, arg1: str = "None", arg2: str = "None"):
        await interaction.response.defer(ephemeral=True)
        await APIH.retrieve_pokedex_data(self.__bot, interaction, arg1, arg2)

    @app_commands.command(name="counter", description="Get counters for a raid boss.")
    async def counter(self, interaction: discord.Interaction, tier: str = "None", name: str = "None", weather: str = "Clear"):
        await interaction.response.defer(ephemeral=True)
        await APIH.get_counter(self.__bot, interaction, tier, name, weather)

    @app_commands.command(name="close", description="Allows a user to manually delete their lobby.")
    async def close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Using interaction.user since we reverted host_manual_remove_lobby to take a user object!
        await RLM.host_manual_remove_lobby(self.__bot, interaction.user)
        try:
            await interaction.followup.send("Lobby close command processed.", ephemeral=True)
        except discord.DiscordException:
            pass

    @app_commands.command(name="extend", description="Allows a user to manually extend the time of their lobby.")
    async def extend(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await RLM.extend_duration_of_lobby(self.__bot, interaction.user)
        try:
            await interaction.followup.send("Lobby extend command processed.", ephemeral=True)
        except discord.DiscordException:
            pass

    @app_commands.command(name="list_names", description="Shows all trainer names in a copy/paste format.")
    async def list_names(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await RLH.show_raider_names(self.__bot, interaction)

    @app_commands.command(name="raid_bosses", description="Gives a list of all raid bosses as per Pokebattler.")
    async def raid_bosses(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        raids = self.__bot.dex.raids or {}
        shadow = []
        normal = []

        for boss_name, raid_data in raids.items():
            display = (boss_name or "").strip().title()
            if not display:
                continue
            tier = (raid_data or {}).get("tier") or ""
            if isinstance(tier, str) and tier.endswith("_SHADOW"):
                shadow.append(f"Shadow {display}")
            else:
                normal.append(display)

        shadow.sort()
        normal.sort()

        embed = discord.Embed(title="Raid Bosses")
        if normal:
            embed.add_field(name="Raids", value="\n".join(normal), inline=False)
        if shadow:
            embed.add_field(name="Shadow Raids", value="\n".join(shadow), inline=False)
        if not normal and not shadow:
            embed.description = "No raid bosses cached. Try `/refresh_raids`."

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="refresh_raids", description="Refresh the cached raids list from Pokebattler.")
    @app_commands.default_permissions(manage_messages=True)
    async def refresh_raids(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            await asyncio.to_thread(self.__bot.dex.update_raids_cache)
        except Exception as e:
            await interaction.followup.send(f"Failed to refresh raids: `{type(e).__name__}`", ephemeral=True)
            return

        bosses = self.__bot.dex.current_raid_bosses()
        preview = ", ".join(bosses[:15]) + (" ..." if len(bosses) > 15 else "")
        await interaction.followup.send(f"Refreshed raids. Bosses cached: **{len(bosses)}**\n{preview}", ephemeral=True)

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(GeneralCommands(bot))
