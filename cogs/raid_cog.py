import asyncio

import discord
from discord.ext import commands

import handlers.raid_handler as RH

class RaidPost(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot

    @commands.command(aliases=["r", "Raid", "R"])
    @commands.guild_only()
    async def raid(self,
                   ctx,
                   tier = "`No tier provided`",
                   pokemon_name = "`No Pokemon Name provided`",
                   weather = "`No weather condition provided`",
                   invite_slots = "5"):

        """Post a raid"""
        print("[i] Processing raid.")
        await asyncio.gather(RH.process_raid(ctx, self.__bot, tier, pokemon_name, weather, invite_slots),
                             self.__bot.delete_ignore_error(ctx.message))

def setup(bot):
    """Default setup function for file"""
    bot.add_cog(RaidPost(bot))
