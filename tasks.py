"""
Contains async task entry task entry points.
"""
import asyncpg
import os
from os import environ
from dotenv import load_dotenv

import classes.database as database
from handlers import startup_handler as SH
from os import environ
from dotenv import load_dotenv

async def startup_process(bot):
    load_dotenv()
    """
    DATABASE: name of the database
    """
    
    """Startup process. Linear process."""
    pool = await asyncpg.create_pool(database=os.getenv('DATABASE'),
                                     port=os.getenv('PORT'),
                                     host=os.getenv('HOST'),
                                     user=os.getenv('DB_USER'),
                                     password=os.getenv('PASSWORD'))
    bot.database = database.Database(pool)
    await bot.wait_until_ready()
    #bot.pool = await init_pool()
    await SH.set_up_guild_raid_counters(bot)

    if bot.live:
        await SH.spin_up_message_deletions(bot)

async def status_update_loop(bot):
    """Updates status continually every ten minutes."""
    await bot.wait_until_ready()
    await SH.start_status_update_loop(bot)

async def lobby_removal_loop(bot):
    """Removes lobbies as their time expires."""
    await bot.wait_until_ready()
    await SH.start_lobby_removal_loop(bot)

async def applicant_loop(bot):
    """Processes raid applicants and adds them to raids."""
    await bot.wait_until_ready()
    await SH.start_applicant_loop(bot)
