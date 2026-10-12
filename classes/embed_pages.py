import discord

class EmbedPages(discord.ui.View):
    """◀ / ▶ through a list of embeds."""
    def __init__(self, embeds, timeout=600):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.page = 0
        self.message = None
        if len(embeds) < 2:
            self.clear_items()
        self._sync()

    def _sync(self):
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page == len(self.embeds) - 1

    async def _turn(self, interaction, step):
        self.page += step
        self._sync()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, -1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn(interaction, 1)

    async def send(self, interaction: discord.Interaction, **kwargs):
        self.message = await interaction.followup.send(embed=self.embeds[0], view=self, wait=True, **kwargs)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.DiscordException:
                pass
