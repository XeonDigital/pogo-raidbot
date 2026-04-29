"""Cog containing administrative commands"""
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import handlers.raid_handler as RH
import handlers.raid_lobby_handler as RLH
import handlers.request_handler as REQH

class AdminCommands(commands.Cog):
    """Admin Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="clear_raid", description="Mod Only - Removes a given user from their raid. Deletes database entry.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_messages=True)
    async def clear_raid(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True)
        await RH.handle_clear_user_from_raid(interaction, self.__bot, user_id)
        await interaction.followup.send(f"Cleared raid for ID [{user_id}].", ephemeral=True)


    @app_commands.command(name="clear_requests", description="Mod Only - Clears all requests for this guild.")
    @app_commands.guild_only()
    @app_commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def clear_requests(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await REQH.handle_clear_all_requests_for_guild(interaction, self.__bot)
        await interaction.followup.send("Cleared all requests for this guild.", ephemeral=True)

    @app_commands.command(name="clear_application", description="Mod Only - Clears an application for a specific user by ID.")
    @app_commands.guild_only()
    @app_commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def clear_application(self, interaction: discord.Interaction, user_id: str):
        await interaction.response.defer(ephemeral=True)
        await RLH.handle_manual_clear_application(interaction, user_id, self.__bot)
        await interaction.followup.send(f"Cleared application for ID [{user_id}].", ephemeral=True)
        
    # im not removing this bcs idk what its for

    # @commands.command()
    # @commands.guild_only()
    # @commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    # async def clear_lobby(self, ctx, user_id):
    #     """Mod Only - Clears an application for a specific user by ID"""
    #     await asyncio.gather(RLH.handle_admin_clear_lobby(ctx, user_id, self.__bot),
    #                          self.__bot.delete_ignore_error(ctx.message))
    
    @app_commands.command(name="a_close", description="Mod Only - Flags a raid lobby for closure.")
    @app_commands.guild_only()
    @app_commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def a_close(self, interaction: discord.Interaction, channel_id: str = ""):
        await interaction.response.defer(ephemeral=True)
        await RLH.handle_admin_close_lobby(interaction, self.__bot, channel_id)
        await interaction.followup.send("Flagged raid lobby for closure.", ephemeral=True)

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(AdminCommands(bot))
