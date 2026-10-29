import asyncio
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import handlers.raid_handler as RH

class RaidPost(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="raid", description="Post a raid")
    @app_commands.guild_only()
    @app_commands.describe(
        pokemon_name="The raid boss you're hosting",
        weather="In-game weather. Defaults to unknown.",
        invite_slots="Open party slots",
        tier="Raid tier. Only needed if the same boss is in more than one tier.",
    )
    async def raid(self,
                   interaction: discord.Interaction,
                   pokemon_name: str,
                   weather: str = "unknown",
                   invite_slots: int = 5,
                   tier: Optional[str] = None):

        """Post a raid"""
        print("[i] Processing raid.")
        await interaction.response.defer(ephemeral=True)
        await asyncio.gather(RH.process_raid(interaction, self.__bot, tier, pokemon_name, weather, str(invite_slots)))

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(RaidPost(bot))
