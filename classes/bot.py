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


class Bot(commands.Bot):
    """
    Subclasses commands.Bot from discord.
    Contains database and asyncio events directly.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.help_command = None # Disable legacy text-based help

        self.applicant_trigger = asyncio.Event()
        self.lobby_remove_trigger = asyncio.Event()
        self._startup_complete = False

        self.database = None
        self.dex = pokedex.Pokedex()
        self.raid_channel_cache = set()
        self.request_channel_cache = set()
        self.guild_raid_counters = {}

    async def setup_hook(self):
        # syncing commands globally
        await self.tree.sync()
        # do we wanna print to show everything is synced properly lol
        # just add print statement here if u want it

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
