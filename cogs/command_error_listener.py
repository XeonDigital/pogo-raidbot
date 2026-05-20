import sys
import traceback
import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

class CommandErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.__bot = bot
        bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if interaction.command is not None and hasattr(interaction.command, 'on_error'):
            print(f"[!]A error occured when running a slash command: {error}")
            return

        error = getattr(error, 'original', error)

        ignored = (app_commands.CommandNotFound, )
        if isinstance(error, ignored):
            return

        message = "An error occurred while executing the command."

        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"This command is on cooldown. Try again in {error.retry_after:.2f}s."
        elif isinstance(error, app_commands.MissingPermissions):
            missing = ", ".join(error.missing_permissions)
            message = f"You are missing the following permissions to run this command: {missing}"
        elif isinstance(error, app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            message = f"I am missing the following permissions to execute this command: {missing}"
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "This command cannot be used in Private Messages."
        elif isinstance(error, asyncpg.PostgresError):
            message = f"A database error occurred while processing your command: [{error}]"
        else:
            print(f'Ignoring exception in command {interaction.command}:', file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.DiscordException:
            pass

async def setup(bot):
    await bot.add_cog(CommandErrorHandler(bot))