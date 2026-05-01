"""Cog containing registration commands"""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import handlers.registration_handler as REGH

class RegistrationCommands(commands.Cog):
    """Registration Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="register_request_channel", description="Mod Only - Sets up channel to allow Pokemon requests.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True, manage_roles=True)
    async def register_request_channel(self, interaction: discord.Interaction):
        """Mod Only - Sets up channel to allow Pokemon requests"""
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(REGH.register_request_channel_handle(interaction, self.__bot))

    @app_commands.command(name="register_raid_channel", description="Mod Only - Sets up channel to allow hosting raids.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True, manage_roles=True)
    async def register_raid_channel(self, interaction: discord.Interaction):
        """Mod Only - Sets up channel to allow hosting raids"""
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(REGH.register_raid_channel_handle(interaction, self.__bot))

    @app_commands.command(name="register_raid_lobby_category", description="Mod Only - Sets up lobby log and category targeting.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def register_raid_lobby_category(self, interaction: discord.Interaction):
        """Mod Only - The channel this command is ran in is set as the log channel for all lobbies. Sets parent category to target for raid lobby creation. A management channel will also be created."""
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(REGH.register_raid_lobby_category(interaction, self.__bot))

    @app_commands.command(name="register_lobby_manager_channel", description="Mod Only - Sets the channel as a lobby management channel.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def register_lobby_manager_channel(self, interaction: discord.Interaction):
        """Mod Only - The channel this command is ran in will be set as a lobby management channel."""
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(REGH.register_lobby_manager_channel(interaction, self.__bot))

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(RegistrationCommands(bot))