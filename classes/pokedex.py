"""
Pokedex class that wraps pokebattler API
"""
from types import SimpleNamespace

import discord

from data import formats as F
from handlers.pokebattler import api_helper as AH
from handlers.pokebattler import pokebattler_api as API
from handlers.pokebattler.pokemon_images import fetch_asset_index
from handlers.pokebattler.pokemon_lookup import DEFAULT_NAMES, build_entries, display_pokemon, find_pokemon, load_cache, max_battle_bosses, save_pokemon
from pogo_raid_lib import normalize_shadow_pokemon_name_for_lookup

RAID_LEVEL_TO_SLASH_TIER = {
    "RAID_LEVEL_1": "1",
    "RAID_LEVEL_1_SHADOW": "1",
    "RAID_LEVEL_3": "3",
    "RAID_LEVEL_3_SHADOW": "3",
    "RAID_LEVEL_5": "5",
    "RAID_LEVEL_5_SHADOW": "5",
    "RAID_LEVEL_ULTRA_BEAST": "5",
    "RAID_LEVEL_ELITE": "5",
    "RAID_LEVEL_MEGA": "mega",
    "RAID_LEVEL_MEGA_5": "mega",
}


def slash_tier_from_raid_level(level):
    return RAID_LEVEL_TO_SLASH_TIER.get(level or "")


def is_shadow_raid(data):
    data = data or {}
    pokemon = data.get("pokemon") or ""
    tier = data.get("tier") or ""
    return "SHADOW" in pokemon or str(tier).endswith("_SHADOW")


def iter_raid_entries(raids):
    for boss_name, data in (raids or {}).items():
        if isinstance(data, list):
            for entry in data:
                yield boss_name, entry or {}
        else:
            yield boss_name, data or {}

class Pokedex():
    def __init__(self):
        self.update_pokemon_cache()
        self.update_moves_cache()
        self.update_raids_cache()

    def update_pokemon_cache(self):
        """Fetch the pokedex and write it to the database."""
        self.pokemon = API.fetch_pokedex()
        try:
            max_battles = max_battle_bosses(API.fetch_raids(), self.pokemon)
        except Exception as error:
            print(f"[!] Could not fetch max battles ({type(error).__name__}); keeping the stored dynamax tags.")
            max_battles = None
        try:
            assets = fetch_asset_index()
        except Exception as error:
            print(f"[!] Could not fetch the sprite listings ({type(error).__name__}); keeping the stored sprite keys.")
            assets = None
        self.pending_pokemon = (self.pokemon, max_battles, assets)

    async def sync_pokemon_list(self, database):
        """Save the staged pokemon, then reload the lookup cache with retry mechanism"""
        try:
            if self.pending_pokemon:
                pokemon, max_battles, assets = self.pending_pokemon
                entries = build_entries(pokemon, DEFAULT_NAMES, max_battles, assets)
                saved = await save_pokemon(database, entries)
                self.pending_pokemon = None
                print(f"[i] Saved {saved} pokemon forms to the database.")
            await load_cache(database)
        except Exception as error:
            print(f"[!] Could not sync the pokemon list ({type(error).__name__}: {error}).")

    def update_moves_cache(self):
        self.moves = API.fetch_moves()

    def update_raids_cache(self):
        self.raids = API.fetch_raids_filtered()

    def current_raid_bosses(self):
        """
        Names accepted by raid/request commands for "currently in rotation".

        - Non-shadow bosses: includes "Boss"
        - Shadow bosses: includes both "Shadow Boss" and "Boss" (so users can type either)
        """
        accepted = set()
        for boss_name, raid_data in iter_raid_entries(self.raids):
            canonical = (boss_name or "").strip()
            if not canonical:
                continue

            display = canonical.title()
            accepted.add(display)

            if is_shadow_raid(raid_data):
                if display.lower().startswith("shadow "):
                    unprefixed = display[7:].strip()
                    if unprefixed:
                        accepted.add(unprefixed.title())
                else:
                    accepted.add(f"Shadow {display}")

        return sorted(accepted)

    @staticmethod
    def normalize_raid_boss_name(name: str) -> str:
        """
        Normalize user input / formatted names for rotation membership checks.
        Delegates to ``normalize_shadow_pokemon_name_for_lookup`` then Title-cases for comparison.
        """
        normalized_name = normalize_shadow_pokemon_name_for_lookup(name)
        if not normalized_name:
            return ""
        return normalized_name.title()

    def is_current_raid_boss(self, name: str) -> bool:
        """
        True if the user-provided boss name matches current rotation.
        Shadow raids accept any spelling that contains ``shadow``; see ``normalize_shadow_pokemon_name_for_lookup``.
        """
        normalized_name = self.normalize_raid_boss_name(name).replace("-", " ")
        if not normalized_name:
            return False
        accepted = {self.normalize_raid_boss_name(n) for n in self.current_raid_bosses()}
        return normalized_name in accepted

    def matching_rotation_bosses(self, pokemon_name):
        """Current-rotation bosses that match the typed name.

        Typing ``shadow`` keeps only shadow forms. Otherwise every matching
        form is returned so a later tier pick can disambiguate.

        Example: rotation has T5 Mewtwo and Shadow T5 Mewtwo.
        ``Mewtwo`` returns both; ``shadow mewtwo`` returns only the shadow form.
        """
        needle = self.normalize_raid_boss_name(pokemon_name).replace("-", " ")
        if not needle:
            return []
        wants_shadow = "shadow" in (pokemon_name or "").lower()
        matches = []
        for boss_name, data in iter_raid_entries(self.raids):
            haystack = self.normalize_raid_boss_name(boss_name).replace("-", " ")
            if haystack != needle:
                continue
            shadow = is_shadow_raid(data)
            if wants_shadow and not shadow:
                continue
            slash_tier = slash_tier_from_raid_level(data.get("tier"))
            if not slash_tier:
                continue
            matches.append(SimpleNamespace(
                name=haystack.title(),
                slash_tier=slash_tier,
                shadow=shadow,
            ))
        return matches

    def get_move_data(self, name):
        move = next((move for move in self.moves if move.get("moveId") == name), None)
        return move

    def get_counter_data(self, name, tier, weather):
        """
        Returns in format:
        [
            {
                key: pokemonId
                key: byMove
                {
                    key: move1
                    key: move2
                }
            },
        ]
        """
        params = {
            b"sort":b"TIME",
            b"weatherCondition":f"{weather}".encode(),
            b"dodgeStrategy":b"DODGE_REACTION_TIME",
            b"aggregation":b"AVERAGE",
            b"includeLegendary":b"true",
            b"includeShadow":b"true",
            b"includeMegas":b"true",
            b"attackerTypes":b"POKEMON_TYPE_ALL",
            b"primalAssistants":b"",
            b"numParty":b"1"
        }
        result, url = API.retrieve_data_from_api(API.link_builder(name, tier, weather), params)
        result = result.get("attackers").pop().get("randomMove").get("defenders")[-1:-7:-1]
        for defender in result:
            moves = defender.get("byMove").pop()
            moves.pop("result")
            for movenum, move in moves.items():
                moves[movenum] = self.get_move_data(move)
            defender["byMove"] = moves
        return result, url

    async def get_counter_for(self, bot, name, tier, weather):
        name_id = self.convert_name_to_id(name, tier)
        tier = tier.upper()
        tier = tier.replace("T","")
        tier_id = f"RAID_LEVEL_{tier}".upper()
        weather_id = F.WEATHER_TO_POKEBATTLER.get((weather or "unknown").lower(), "NO_WEATHER")
        print(f"{name_id}, {tier_id}, {weather_id}")
        result, link = self.get_counter_data(name_id, tier_id, weather_id)
        link = link.replace("fight.", "www.")
        embed = discord.Embed(title=name.replace("-", " ").title(), description="Recommended counters and moves ", url=link)
        embed.add_field(name="Weather", value=F.WEATHER_TO_EMOJI.get(weather.lower()), inline=False)
        embed.add_field(name="Counters", value="With a **random moveset** and the above weather, here are the recommended counters.", inline=False)
        for rank, counter in enumerate(result, start=1):
            name, _ = display_pokemon(counter["pokemonId"])
            embed.add_field(name=f"{rank}) {name}", value="\n".join(AH.counter_moves(counter, AH.TYPE_EMOJIS)), inline=True)
        return embed

    def convert_name_to_id(self, name, tier):
        """Pokebattler id for a name that already passed ``validate_pokemon``."""
        match = find_pokemon(normalize_shadow_pokemon_name_for_lookup(name), mega="mega" in tier.lower())
        return match["pokemon_id"]
