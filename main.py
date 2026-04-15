"""Main bot set up and command set up"""

import argparse
import asyncio
from datetime import datetime
import os
import sys

import asyncpg
import discord
#from discord.ext import commands

import classes.bot as bot
#env libraries
from os import environ
from dotenv import load_dotenv
#import raid_cog


#from . import handlers
from tasks import *

load_dotenv()

DESCRIPTION = '''Pokemon Go Raid Bot'''

#Set command_prefix to any character here.
COMMAND_PREFIX = '-'
#Change this string to change the 'playing' status of the bot.
CUSTOM_STATUS = ""

intent = discord.Intents().default()
intent.members = True
intent.guilds = True
intent.message_content = True

GAME = discord.Game(CUSTOM_STATUS)
BOT = bot.Bot(COMMAND_PREFIX, description=DESCRIPTION, activity=GAME, intents=intent)

BOT.pool = None
BOT.categories_allowed = True
BOT.live = False

#@BOT.event
#async def on_ready():
#    await BOT.loop.create_task(startup_process(BOT))
#    await BOT.loop.create_task(status_update_loop(BOT))
#    await BOT.loop.create_task(applicant_loop(BOT))
#    await BOT.loop.create_task(lobby_removal_loop(BOT))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-l", action="store_true")
    args = parser.parse_args()
    #BOT.loop.create_task(startup_process(BOT))
    #BOT.loop.create_task(status_update_loop(BOT))
    #BOT.loop.create_task(applicant_loop(BOT))
    #BOT.loop.create_task(lobby_removal_loop(BOT))
    if args.l:
        print("[!] Running bot live.")
        BOT.live=True
        BOT.run(os.getenv("LIVE_TOKEN"))
    else:
        print("[i] Running bot in test mode")
        BOT.run(os.getenv('TESTING_TOKEN'))
