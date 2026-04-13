"""Cog containing administrative commands"""
import asyncio

#import discord
from discord.ext import commands

import handlers.raid_handler as RH
import handlers.raid_lobby_handler as RLH
import handlers.request_handler as REQH

class AdminCommands(commands.Cog):
    """Admin Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True)
    async def clear_raid(self, ctx, user_id):
        """Mod Only - Removes a given user from their raid. Deletes database entry."""
        await asyncio.gather(RH.handle_clear_user_from_raid(ctx, self.__bot, user_id),
                             self.__bot.delete_ignore_error(ctx.message))


    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def clear_requests(self, ctx):
        """Mod Only - Clears all requests for this guild."""
        await asyncio.gather(REQH.handle_clear_all_requests_for_guild(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True)
    async def clear_application(self, ctx, user_id):
        """Mod Only - Clears an application for a specific user by ID"""
        await asyncio.gather(RLH.handle_manual_clear_application(ctx, user_id, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))
        
    # @commands.command()
    # @commands.guild_only()
    # @commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    # async def clear_lobby(self, ctx, user_id):
    #     """Mod Only - Clears an application for a specific user by ID"""
    #     await asyncio.gather(RLH.handle_admin_clear_lobby(ctx, user_id, self.__bot),
    #                          self.__bot.delete_ignore_error(ctx.message))
    
    @commands.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_messages=True, manage_roles=True, manage_channels=True)
    async def a_close(self, ctx, channel_id=""):
        """Mod Only - Flags a raid lobby for closure."""
        await asyncio.gather(RLH.handle_admin_close_lobby(ctx, self.__bot, channel_id),
                             self.__bot.delete_ignore_error(ctx.message))

def setup(bot):
    """Default setup function for file"""
    bot.add_cog(AdminCommands(bot))
