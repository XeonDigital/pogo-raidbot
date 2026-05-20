"""Cog containing member commands"""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import handlers.helpers as H
import handlers.raid_handler as RH
import handlers.request_handler as REQH

class MemberCommands(commands.Cog):
    """Members Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="request", description="Processes a users pokemon request")
    @app_commands.guild_only()
    async def request(self, interaction: discord.Interaction, tier: str = None, pokemon_name: str = None):
        """Processes a users pokemon request"""
        if not await REQH.check_if_valid_request_channel(self.__bot, interaction.channel.id):
            await interaction.response.send_message(H.guild_member_dm(interaction.guild.name, "That channel is not a valid request channel."), ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await REQH.request_pokemon_handle(self.__bot, interaction, tier, pokemon_name)

    @app_commands.command(name="raid_count", description="Show total raids hosted in this server")
    @app_commands.guild_only()
    async def raid_count(self, interaction: discord.Interaction):
        """Show total raids hosted in this server"""
        await interaction.response.defer(ephemeral=True)
        await RH.get_raid_count(self.__bot, interaction, True)


async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(MemberCommands(bot))
