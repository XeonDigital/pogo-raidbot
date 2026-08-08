"""Cog containing event listeners"""
from discord.ext import commands

import handlers.events as EH

class Listeners(commands.Cog):
    """Event Listeners Cog"""
    def __init__(self, bot):
        self.__bot = bot
        # on_ready can fire again on reconnect; only sync slash commands once per process.
        self._has_synced = False

    @commands.Cog.listener()
    async def on_ready(self):
        """Built in event"""
        print(f'[i] Logged in as {self.__bot.user.name} \n')
        print(f'[i] Connected guilds: {[f"{g.name} ({g.id})" for g in self.__bot.guilds]}')

        # Skip re-syncing on later on_ready calls to avoid Discord rate limits.
        if self._has_synced:
            return

        try:
            # Guild sync shows commands immediately; global sync can take up to an hour.
            # copy_global_to is required so guild sync includes the global command tree.
            for guild in self.__bot.guilds:
                self.__bot.tree.copy_global_to(guild=guild)
                synced = await self.__bot.tree.sync(guild=guild)
                print(f"[i] Synced {len(synced)} commands to guild {guild.name} ({guild.id}).")
            synced = await self.__bot.tree.sync()
            print(f"[i] Synced {len(synced)} commands globally.")
            self._has_synced = True
        except Exception as error:
            print(f"Failed to sync commands: {error}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Built in event"""
        await EH.raw_reaction_add_handle(payload, self.__bot)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        """Built in event"""
        await EH.raw_message_delete_handle(payload, self.__bot)

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
            print(f'An exception occurred during message handling. [{error}]')


async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(Listeners(bot))
