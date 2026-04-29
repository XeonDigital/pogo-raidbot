"""
Bot class that wraps discord client
"""
import asyncio
import os
from os import environ
import sys
import discord
from discord.ext import commands

from tasks import *
import classes.database as database
import classes.pokedex as pokedex
#from classes import database
#from classes import pokedex


class CategorySortedHelpCommand(commands.HelpCommand):
    """
    Custom `help` with stable sections (Admin / General / Other).

    discord.py invokes `send_bot_help(mapping)` for bare `help`. `mapping` is
    `{ cog_or_None: [commands registered on that cog] }`; commands with no cog are under `None`.

    We match two cog classes by **qualified_name** (same as the Python class name of each
    `@commands.Cog`). Commands from every other cog are grouped under "Other".

    `filter_commands()` drops hidden commands and commands the invoker cannot run.
    """

    async def send_bot_help(self, mapping):
        ctx = self.context
        if ctx is None:
            return

        # Prefix as shown to users (handles mention-style prefixes correctly).
        prefix = getattr(ctx, "clean_prefix", None) or ""

        # Cog class name -> embed section title. List order is section order on screen.
        category_order = [
            ("AdminCommands", "Admin Commands"),
            ("GeneralCommands", "General Commands"),
        ]

        def cog_key(cog):
            # Cog.qualified_name is the class name, e.g. "GeneralCommands".
            return getattr(cog, "qualified_name", None) if cog else None

        embed = discord.Embed(title="Help")
        embed.description = f"Use `{prefix}help <command>` for details."

        for cog_name, title in category_order:
            cog = next((c for c in mapping.keys() if cog_key(c) == cog_name), None)
            cmds = mapping.get(cog) or []
            # Alphabetical by primary command name (not aliases).
            filtered = await self.filter_commands(cmds, sort=True, key=lambda c: c.name)
            if not filtered:
                continue

            lines = [f"`{prefix}{c.name}`" for c in filtered]
            embed.add_field(name=title, value=" ".join(lines), inline=False)

        # Raid cog, registration, etc.: anything not listed in category_order.
        other_cmds = []
        for cog, cmds in mapping.items():
            if cog_key(cog) in {c for c, _ in category_order}:
                continue
            other_cmds.extend(cmds or [])
        other_filtered = await self.filter_commands(other_cmds, sort=True, key=lambda c: c.name)
        if other_filtered:
            lines = [f"`{prefix}{c.name}`" for c in other_filtered]
            embed.add_field(name="Other", value=" ".join(lines), inline=False)

        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        """Per-command help: `help <name>` shows usage, docstring, and aliases."""
        ctx = self.context
        if ctx is None:
            return

        prefix = getattr(ctx, "clean_prefix", None) or ""
        # Includes subcommand path if this command lives under a Group.
        signature = f"{prefix}{command.qualified_name} {command.signature}".strip()
        embed = discord.Embed(title=f"Help: {command.qualified_name}")
        embed.add_field(name="Usage", value=f"`{signature}`", inline=False)
        if command.help:
            embed.add_field(name="Description", value=command.help, inline=False)
        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in command.aliases), inline=False)
        await ctx.send(embed=embed)


class Bot(commands.Bot):
    """
    Subclasses commands.Bot from discord.
    Contains database and asyncio events directly.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Swap discord.py's default HelpCommand for our categorized embed help (see CategorySortedHelpCommand).
        self.help_command = CategorySortedHelpCommand()

        self.applicant_trigger = asyncio.Event()
        self.lobby_remove_trigger = asyncio.Event()
        self._startup_complete = False

        self.database = None
        self.dex = pokedex.Pokedex()
        self.raid_channel_cache = set()
        self.request_channel_cache = set()
        self.guild_raid_counters = {}

    async def on_ready(self) -> None:
        # discord.py may call on_ready more than once (e.g. reconnect/resume).
        # Ensure we only spawn background tasks once.
        if self._startup_complete:
            return
        self._startup_complete = True

        self.loop.create_task(startup_process(self))
        self.loop.create_task(status_update_loop(self))
        self.loop.create_task(applicant_loop(self))
        self.loop.create_task(lobby_removal_loop(self))

    async def retrieve_channel(self, *args, **kwargs):
        """
        Automatically fetches channel if channel is not in local cache.
        Virtually guarantees getting channel object if it does exist and bot can see it.
        """
        channel = self.get_channel(*args, **kwargs)
        if not channel:
            try:
                channel = await self.fetch_channel(*args, **kwargs)
            except discord.DiscordException:
                pass

        return channel

    async def retrieve_user(self, *args, **kwargs):
        """
        Automatically fetches a user if the user is not in the local cache.
        Virtually guarantees getting user object if it does exist and the bot can see it.
        """
        user = self.get_user(*args, **kwargs)
        if not user:
            try:
                user = await self.fetch_user(*args, **kwargs)
            except discord.DiscordException:
                pass

        return user

    async def delete_ignore_error(self, item):
        try:
            await item.delete()
        except discord.DiscordException:
            return
        except AttributeError:
            # Ignore if item doesn't have delete method
            return

    async def remove_role_ignore_error(self, member, role, reason):
        try:
            await member.remove_roles(role, reason=reason)
        except discord.DiscordException:
            pass
        except AttributeError:
            #Ignore if object doesn't have "remove_roles" method
            pass

    async def add_role_ignore_error(self, member, role, reason):
        try:
            await member.add_roles(role, reason=reason)
        except discord.DiscordException:
            pass
        except AttributeError:
            pass

    async def send_ignore_error(self, messageable, text, embed=None, delete_after=None):
        try:
            await messageable.send(text, embed=embed, delete_after=delete_after)
        except discord.DiscordException:
            pass
        except AttributeError:
            pass
