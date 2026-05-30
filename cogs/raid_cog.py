import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import handlers.raid_handler as RH

class RaidPost(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="raid", description="Post a raid")
    @app_commands.guild_only()
    async def raid(self,
                   interaction: discord.Interaction,
                   tier: str = "No tier provided",
                   pokemon_name: str = "No Pokemon Name provided",
                   weather: str = "No weather condition provided",
                   invite_slots: int = 5):

        """Post a raid"""
        print("[i] Processing raid.")
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(RH.process_raid(interaction, self.__bot, tier, pokemon_name, weather, str(invite_slots)))

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(RaidPost(bot))
