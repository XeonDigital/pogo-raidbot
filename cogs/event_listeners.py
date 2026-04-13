"""Cog containing event listeners"""
from discord.ext import commands

import handlers.events as EH

class Listeners(commands.Cog):
    """Event Listeners Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Built in event"""
        print(f'[i] Logged in as {self.__bot.user.name} \n')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, ctx):
        """Built in event"""
        await EH.raw_reaction_add_handle(ctx, self.__bot)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, ctx):
        """Built in event"""
        await EH.raw_message_delete_handle(ctx, self.__bot)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Built in event"""
        await EH.on_guild_channel_delete(channel, self.__bot)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Built in event"""
        try:
            await EH.on_message_handle(message, self.__bot)
        except Exception as error:
            print(f'[!] An exception occurred during message handling. [{error}]')


def setup(bot):
    """Default setup function for file"""
    bot.add_cog(Listeners(bot))
