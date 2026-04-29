"""Cog containing general commands"""
import asyncio
import time

import discord
from discord.ext import commands

import handlers.friend_code_handler as FCH
import handlers.pokebattler.api_helper as APIH
import handlers.raid_lobby_handler as RLH
import handlers.raid_lobby_management as RLM

class GeneralCommands(commands.Cog):
    """General Commands Cog"""
    def __init__(self, bot):
        self.__bot = bot

    @commands.command()
    async def ping(self, ctx):
        """Check if alive"""
        curr = time.time()
        latency: float = round(ctx.bot.latency * 1000.0, 2)
        msg = await ctx.send('Pinging... 🏓')
        await msg.edit(
            content=f'🏓 Pong! Latency is {round((time.time() - curr) * 1000.0, 2)}ms. API latency is {latency}ms.')

    @commands.command(aliases=["fcreg", "set_fc", "sf", "Setfc"])
    async def setfc(self, ctx):
        """Allows a user to register their Pokemon Go friend code."""
        await asyncio.gather(FCH.set_friend_code(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["sn", "Sn", "Setname"])
    async def setname(self, ctx, name=""):
        """Allows a user to register their Pokemon Go trainer name."""
        await asyncio.gather(FCH.set_trainer_name(ctx, self.__bot, name),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["sl", "Sl", "Setlevel"])
    async def setlevel(self, ctx, level):
        """Allows a user to register their Pokemon Go trainer level."""
        await asyncio.gather(FCH.set_trainer_level(ctx, self.__bot, level),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    async def fc(self, ctx):
        """Sends registered friend code to the channel the command was typed in."""
        await asyncio.gather(FCH.send_friend_code(ctx, self.__bot),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["t", "T"])
    async def trainer(self, ctx, user_id="0"):
        """Sends trainer information to current channel."""
        await asyncio.gather(FCH.send_trainer_information(ctx, self.__bot, user_id),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    async def set_level(self, ctx, level):
        """Sets the trainer's level in the database"""
        await asyncio.gather(FCH.set_trainer_level(ctx, self.__bot, level),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command()
    async def dex(self, ctx, arg1="None", arg2="None"):
        """Retrieves Pokedex information for a given Pokedex number or Pokemon Name"""
        await asyncio.gather(APIH.retrieve_pokedex_data(self.__bot, ctx, arg1, arg2),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["c", "C"])
    async def counter(self, ctx, tier="None", name="None", weather="Clear"):
        await asyncio.gather(APIH.get_counter(self.__bot, ctx, tier, name, weather),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["Close"])
    async def close(self, ctx):
        """Allows a user to manually delete their lobby via command."""
        ctx.user_id = ctx.author.id
        await asyncio.gather(RLM.host_manual_remove_lobby(self.__bot, ctx),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["Extend"])
    async def extend(self, ctx):
        """Allows a user to manually extend the time of their lobby via command."""
        ctx.user_id = ctx.author.id
        await asyncio.gather(RLM.extend_duration_of_lobby(self.__bot, ctx),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["ln", "Ln", "LN", "List_names"])
    async def list_names(self, ctx):
        """Shows all trainer names in a copy/paste format for searching in game."""
        ctx.user_id = ctx.author.id
        await asyncio.gather(RLH.show_raider_names(self.__bot, ctx),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["raids", "bosses"])
    async def raid_bosses(self, ctx):
        """Gives a list of all raid bosses as per the Pokebattler API"""
        raids = self.__bot.dex.raids or {}
        shadow = []
        normal = []

        for boss_name, raid_data in raids.items():
            display = (boss_name or "").strip().title()
            if not display:
                continue
            tier = (raid_data or {}).get("tier") or ""
            if isinstance(tier, str) and tier.endswith("_SHADOW"):
                shadow.append(f"Shadow {display}")
            else:
                normal.append(display)

        shadow.sort()
        normal.sort()

        embed = discord.Embed(title="Raid Bosses")
        if normal:
            embed.add_field(name="Raids", value="\n".join(normal), inline=False)
        if shadow:
            embed.add_field(name="Shadow Raids", value="\n".join(shadow), inline=False)
        if not normal and not shadow:
            embed.description = "No raid bosses cached. Try `refresh_raids`."

        await asyncio.gather(self.__bot.send_ignore_error(ctx, " ", embed=embed),
                             self.__bot.delete_ignore_error(ctx.message))

    @commands.command(aliases=["update_raids", "reload_raids"])
    async def refresh_raids(self, ctx):
        """
        Refresh the cached raids list from Pokebattler without restarting the bot.
        Runs the network call in a worker thread to avoid blocking the event loop.
        """
        await asyncio.gather(self.__bot.delete_ignore_error(ctx.message))

        try:
            await asyncio.to_thread(self.__bot.dex.update_raids_cache)
        except Exception as e:
            await self.__bot.send_ignore_error(ctx, f"Failed to refresh raids: `{type(e).__name__}`")
            return

        bosses = self.__bot.dex.current_raid_bosses()
        preview = ", ".join(bosses[:15]) + (" ..." if len(bosses) > 15 else "")
        await self.__bot.send_ignore_error(
            ctx,
            f"Refreshed raids. Bosses cached: **{len(bosses)}**\n{preview}"
        )

async def setup(bot):
    """Default setup function for file"""
    await bot.add_cog(GeneralCommands(bot))
