"""Cog containing general commands"""
import asyncio
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import handlers.friend_code_handler as FCH
import handlers.pokebattler.api_helper as APIH
import handlers.pokebattler.pokebattler_dex as DEX
import handlers.raid_lobby_handler as RLH
import handlers.raid_lobby_management as RLM

DEX_TYPES = ("BUG", "DARK", "DRAGON", "ELECTRIC", "FAIRY", "FIGHTING", "FIRE", "FLYING", "GHOST",
             "GRASS", "GROUND", "ICE", "NORMAL", "POISON", "PSYCHIC", "ROCK", "STEEL", "WATER")
DEX_FORM_CHOICES = [app_commands.Choice(name=option.title(), value=option) for option in DEX.TAG_FILTERS]


class GeneralCommands(commands.Cog):
    """General Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @app_commands.command(name="ping", description="Check if the bot is alive and latency.")
    async def ping(self, interaction: discord.Interaction):
        curr = time.time()
        latency: float = round(self.__bot.latency * 1000.0, 2)
        await interaction.response.send_message('Pinging... 🏓', ephemeral=True)
        msg = await interaction.original_response()
        await msg.edit(
            content=f'🏓 Pong! Latency is {round((time.time() - curr) * 1000.0, 2)}ms. API latency is {latency}ms.')

    @app_commands.command(name="setfc", description="Allows a user to register their Pokemon Go friend code.")
    async def setfc(self, interaction: discord.Interaction, fc: str):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_friend_code(interaction, self.__bot, fc)

    @app_commands.command(name="setname", description="Allows a user to register their Pokemon Go trainer name.")
    async def setname(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_trainer_name(interaction, self.__bot, name)

    @app_commands.command(name="setlevel", description="Allows a user to register their Pokemon Go trainer level.")
    async def setlevel(self, interaction: discord.Interaction, level: int):
        await interaction.response.defer(ephemeral=True)
        await FCH.set_trainer_level(interaction, self.__bot, level)

    @app_commands.command(name="fc", description="Sends your registered friend code to the channel.")
    async def fc(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await FCH.send_friend_code(interaction, self.__bot)

    @app_commands.command(name="trainer", description="Look up trainer information.")
    async def trainer(self, interaction: discord.Interaction, user_id: str = "0"):
        await interaction.response.defer(ephemeral=True)
        await FCH.send_trainer_information(interaction, self.__bot, user_id)

    @app_commands.command(name="dex", description="List Pokemon forms by name or dex number, with optional filters.")
    @app_commands.describe(
        name="Pokemon name, alias or dex number (lists all of its forms)",
        only="Only list these forms",
        hide="Leave these forms out",
        type="Only forms with this type",
        rarity="Only legendary, mythic or ultra beast species",
        shiny="Show shiny sprites",
    )
    @app_commands.choices(
        only=DEX_FORM_CHOICES,
        hide=DEX_FORM_CHOICES,
        type=[app_commands.Choice(name=t.title(), value=t) for t in DEX_TYPES],
        rarity=[app_commands.Choice(name=r.replace("_", " ").title(), value=r) for r in ("LEGENDARY", "MYTHIC", "ULTRA_BEAST")],
        shiny=[app_commands.Choice(name="Yes", value=1), app_commands.Choice(name="No", value=0)],
    )
    async def dex(self, interaction: discord.Interaction, name: Optional[str] = None,
                  only: Optional[app_commands.Choice[str]] = None, hide: Optional[app_commands.Choice[str]] = None,
                  type: Optional[app_commands.Choice[str]] = None, rarity: Optional[app_commands.Choice[str]] = None,
                  shiny: Optional[app_commands.Choice[int]] = None):
        await interaction.response.defer(ephemeral=True)
        await DEX.send_dex(self.__bot, interaction, name,
                           only=only.value if only else None, hide=hide.value if hide else None,
                           type_=type.value if type else None, rarity=rarity.value if rarity else None,
                           shiny=bool(shiny and shiny.value))

    @app_commands.command(name="counter", description="Get counters for a raid boss.")
    async def counter(self, interaction: discord.Interaction, tier: str = "None", name: str = "None", weather: str = "Clear"):
        await interaction.response.defer(ephemeral=True)
        await APIH.get_counter(self.__bot, interaction, tier, name, weather)

    @app_commands.command(name="close", description="Allows a user to manually delete their lobby.")
    async def close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # Using interaction.user since we reverted host_manual_remove_lobby to take a user object!
        await RLM.host_manual_remove_lobby(self.__bot, interaction.user)
        try:
            await interaction.followup.send("Lobby close command processed.", ephemeral=True)
        except discord.DiscordException:
            pass

    @app_commands.command(name="extend", description="Allows a user to manually extend the time of their lobby.")
    @app_commands.describe(minutes="Minutes to add. Defaults to 10.")
    async def extend(self, interaction: discord.Interaction, minutes: Optional[app_commands.Range[int, 1, 45]] = None):
        await interaction.response.defer(ephemeral=True)
        await RLM.extend_duration_of_lobby(self.__bot, interaction.user, minutes=minutes)
        try:
            await interaction.followup.send("Lobby extend command processed.", ephemeral=True)
        except discord.DiscordException:
            pass

    @app_commands.command(name="list_names", description="Shows all trainer names in a copy/paste format.")
    async def list_names(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await RLH.show_raider_names(self.__bot, interaction)

    @app_commands.command(name="raid_bosses", description="Gives a list of all raid bosses as per Pokebattler.")
    async def raid_bosses(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        raids = self.__bot.dex.raids or {}
        tier1 = []
        tier3 = []
        tier5 = []
        mega = []
        sha_tier1 = []
        sha_tier3 = []
        sha_tier5 = []

        for boss_name, raid_data in raids.items():
            display = (boss_name or "").strip().title()
            if not display:
                continue
            tier = (raid_data or {}).get("tier") or ""
            if "SHADOW" not in raid_data.get("pokemon"):
                match tier:
                    case "RAID_LEVEL_1":
                        tier1.append(display)
                    case "RAID_LEVEL_3":
                        tier3.append(display)
                    case "RAID_LEVEL_5" | "RAID_LEVEL_ULTRA_BEAST":
                        tier5.append(display)
                    case "RAID_LEVEL_MEGA" | "RAID_LEVEL_ELITE":
                        mega.append(display)
                    
            else:
                match tier:
                    case "RAID_LEVEL_1_SHADOW" | "RAID_LEVEL_1":
                        sha_tier1.append(display)
                    case "RAID_LEVEL_3_SHADOW" | "RAID_LEVEL_3":
                        sha_tier3.append(display)
                    case "RAID_LEVEL_5_SHADOW" | "RAID_LEVEL_5":
                        sha_tier5.append(display)

        tier1.sort()
        tier3.sort()
        tier5.sort()
        mega.sort()
        sha_tier1.sort()
        sha_tier3.sort()
        sha_tier5.sort()

        embed = discord.Embed(title="Raid Bosses")
        
        if tier1 and tier3 and tier5 and mega and sha_tier1 and sha_tier3 and sha_tier5:
            embed.add_field(name="Mega", value="\n".join(mega), inline=False)
            embed.add_field(name="Tier 5 ", value="\n".join(tier5), inline=False)
            embed.add_field(name="Tier 3", value="\n".join(tier3), inline=False)
            embed.add_field(name="Tier 1", value="\n".join(tier1), inline=False)
            embed.add_field(name="Shadow Tier 5", value="\n".join(sha_tier5), inline=False)
            embed.add_field(name="Shadow Tier 3", value="\n".join(sha_tier3), inline=False)
            embed.add_field(name="Shadow Tier 1", value="\n".join(sha_tier1), inline=False)
        else:
            embed.description = "No raid bosses cached. Try `/refresh_raids`."
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="refresh_raids", description="Refresh the cached raids list from Pokebattler.")
    @app_commands.default_permissions(manage_messages=True)
    async def refresh_raids(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            await asyncio.to_thread(self.__bot.dex.update_raids_cache)
        except Exception as e:
            await interaction.followup.send(f"Failed to refresh raids: `{type(e).__name__}`", ephemeral=True)
            return

        bosses = self.__bot.dex.current_raid_bosses()
        preview = ", ".join(bosses[:15]) + (" ..." if len(bosses) > 15 else "")
        await interaction.followup.send(f"Refreshed raids. Bosses cached: **{len(bosses)}**\n{preview}", ephemeral=True)

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(GeneralCommands(bot))
