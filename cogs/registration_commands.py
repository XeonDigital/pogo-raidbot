"""Cog containing registration commands"""
import asyncio

#import discord
from discord.ext import commands

import handlers.registration_handler as REGH

class RegistrationCommands(commands.Cog):
    """Registration Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def register_request_channel(self, ctx):
        """Mod Only - Sets up channel to allow Pokemon requests"""
        await asyncio.gather(REGH.register_request_channel_handle(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def register_raid_channel(self, ctx):
        """Mod Only - Sets up channel to allow hosting raids"""
        await asyncio.gather(REGH.register_raid_channel_handle(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def register_raid_lobby_category(self, ctx):
        """Mod Only - The channel this command is ran in is set as the log channel for all lobbies. Sets parent category to target for raid lobby creation. A management channel will also be created."""
        await asyncio.gather(REGH.register_raid_lobby_category(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def register_lobby_manager_channel(self, ctx):
        """Mod Only - The channel this command is ran in will be set as a lobby management channel."""
        await asyncio.gather(REGH.register_raid_lobby_manager_channel(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

def setup(bot):
    """Default setup function for file"""
    bot.add_cog(RegistrationCommands(bot))