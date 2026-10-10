import discord

from handlers.pokebattler.pokemon_images import image_url
from handlers.pokebattler.pokemon_lookup import find_pokemon, suggest_pokemon
from pogo_raid_lib import normalize_shadow_pokemon_name_for_lookup

PAGE_SIZE = 10

TAG_FILTERS = {
    "shadow": "shadow",
    "mega": "mega",
    "gigantamax": "gigantamax",
    "dynamax": "dynamax",
    "costume": "cosmetic",
    "regional": "regional",
}

NOTES = {"shadow": "Can be Shadow", "dynamax": "Can Dynamax"}

# Game master BATTLE_SETTINGS / COMBAT_SETTINGS: applied to base stats in battle, stamina is unchanged.
SHADOW_ATTACK_MULTIPLIER = 1.2
SHADOW_DEFENSE_MULTIPLIER = 0.8333333

SEARCH_FORMS = """
SELECT COALESCE(f.overrides->>'display_name', f.display_name) AS display_name, l.dex_num, f.tags,
       COALESCE(f.overrides->>'icon_key', f.icon_key) AS icon_key,
       COALESCE(f.overrides->>'shiny_icon_key', f.shiny_icon_key) AS shiny_icon_key,
       s.base_attack, s.base_defense, s.base_stamina
FROM pokedex.pokemon_forms f
JOIN pokedex.pokemon_list l ON l.id = f.species_id
LEFT JOIN pokedex.pokemon_stats s ON s.form_id = f.id
WHERE ($1::text IS NULL OR f.species_id = (SELECT species_id FROM pokedex.pokemon_forms WHERE pokebattler_id = $1::text))
  AND ($2::int IS NULL OR l.dex_num = $2::int)
  AND f.tags @> $3::text[]
  AND NOT f.tags && $4::text[]
  AND ($5::text IS NULL OR $5::text = ANY(f.types))
  AND ($6::text IS NULL OR l.rarity = $6::text)
ORDER BY l.dex_num, f.pokebattler_id <> l.pokebattler_id, display_name
"""


def resolve_name(name):
    name = (name or "").strip()
    if name.lstrip("#").isdigit():
        return None, int(name.lstrip("#")), False, None
    wants_shadow = "shadow" in name.lower()
    lookup = normalize_shadow_pokemon_name_for_lookup(name)
    match = find_pokemon(lookup) or find_pokemon(lookup, mega=True)
    if match:
        return match["pokemon_id"], None, wants_shadow, None
    return None, None, wants_shadow, suggest_pokemon(lookup) or suggest_pokemon(lookup, mega=True)


def sprite_url(row, shiny=False):
    return image_url((shiny and row["shiny_icon_key"]) or row["icon_key"])


def form_details(row):
    has_stats = row["base_attack"] is not None
    lines = [f"ATK {row['base_attack']} · DEF {row['base_defense']} · STA {row['base_stamina']}"] if has_stats else []
    for tag, note in NOTES.items():
        if tag not in row["tags"]:
            continue
        if tag == "shadow" and has_stats:
            attack = round(row["base_attack"] * SHADOW_ATTACK_MULTIPLIER)
            defense = round(row["base_defense"] * SHADOW_DEFENSE_MULTIPLIER)
            note = f"{note} (ATK {attack} · DEF {defense} in battle)"
        lines.append(f"• {note}")
    return "\n".join(lines)


class DexPages(discord.ui.View):
    """ to change pages """
    def __init__(self, rows, title, filters_text, shiny=False):
        super().__init__(timeout=300)
        self.pages = [rows[i:i + PAGE_SIZE] for i in range(0, len(rows), PAGE_SIZE)]
        self.total = len(rows)
        self.title = title
        self.filters_text = filters_text
        self.shiny = shiny
        self.page = 0
        self.selected = 0
        if len(self.pages) == 1:
            self.remove_item(self.previous_page)
            self.remove_item(self.next_page)
        if self.total == 1:
            self.remove_item(self.previous)
            self.remove_item(self.next)
        self._sync()

    def _move(self, step):
        position = min(max(self.page * PAGE_SIZE + self.selected + step, 0), self.total - 1)
        self.page, self.selected = divmod(position, PAGE_SIZE)

    def embed(self):
        rows = self.pages[self.page]
        lines = []
        for index, row in enumerate(rows):
            line = f"`#{row['dex_num']:04d}` {row['display_name']}"
            lines.append(f"**{line} ◀**" if index == self.selected else line)
        embed = discord.Embed(title=self.title, description="\n".join(lines))
        selected = rows[self.selected]
        details = form_details(selected)
        if details:
            embed.add_field(name=selected["display_name"], value=details, inline=False)
        embed.set_image(url=sprite_url(selected, self.shiny))
        footer = [f"{self.total} form{'' if self.total == 1 else 's'}"]
        if self.filters_text:
            footer.append(self.filters_text)
        if len(self.pages) > 1:
            footer.append(f"page {self.page + 1}/{len(self.pages)}")
        embed.set_footer(text=" · ".join(footer))
        return embed

    def _sync(self):
        position = self.page * PAGE_SIZE + self.selected
        self.previous.disabled = position == 0
        self.next.disabled = position == self.total - 1
        self.previous_page.disabled = self.page == 0
        self.next_page.disabled = self.page == len(self.pages) - 1
        self.picker.options = [
            discord.SelectOption(label=row["display_name"][:100], value=str(index), description=f"#{row['dex_num']}",
                                 default=index == self.selected)
            for index, row in enumerate(self.pages[self.page])
        ]

    async def _show(self, interaction):
        self._sync()
        await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.select(placeholder="Show a form's sprite", row=0)
    async def picker(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected = int(select.values[0])
        await self._show(interaction)

    @discord.ui.button(label="«", style=discord.ButtonStyle.secondary, row=1)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page, self.selected = self.page - 1, 0
        await self._show(interaction)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=1)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._move(-1)
        await self._show(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=1)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._move(1)
        await self._show(interaction)

    @discord.ui.button(label="»", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page, self.selected = self.page + 1, 0
        await self._show(interaction)


async def send_dex(bot, interaction: discord.Interaction, name=None, only=None, hide=None, type_=None, rarity=None,
                   shiny=False):
    if only and only == hide:
        await interaction.followup.send(f"Can't both only show and hide **{only}** forms.", ephemeral=True)
        return
    pokemon_id = dex_num = None
    if name:
        pokemon_id, dex_num, wants_shadow, suggestion = resolve_name(name)
        if pokemon_id is None and dex_num is None:
            hint = f" Did you mean **{suggestion}**?" if suggestion else ""
            await interaction.followup.send(f"Could not find a pokemon called **{name}**.{hint}", ephemeral=True)
            return
        if wants_shadow and not only and hide != "shadow":
            only = "shadow"
    if not (name or only or hide or type_ or rarity):
        await interaction.followup.send("Give a pokemon name or dex number, or at least one filter.", ephemeral=True)
        return

    required = [TAG_FILTERS[only]] if only else []
    excluded = [TAG_FILTERS[hide]] if hide else []
    rows = await bot.database.fetch(SEARCH_FORMS, pokemon_id, dex_num, required, excluded, type_, rarity)
    if not rows:
        await interaction.followup.send("No pokemon match those filters.", ephemeral=True)
        return

    filters = []
    if only:
        filters.append(f"only: {only.title()}")
    if hide:
        filters.append(f"hide: {hide.title()}")
    if type_:
        filters.append(f"type: {type_.title()}")
    if rarity:
        filters.append(f"rarity: {rarity.replace('_', ' ').title()}")
    if shiny:
        filters.append("shiny sprites")
    title = f"Pokédex · {name.strip().title()}" if name else "Pokédex"
    view = DexPages(rows, title, ", ".join(filters), shiny=shiny)
    await interaction.followup.send(embed=view.embed(), view=view, ephemeral=True)
