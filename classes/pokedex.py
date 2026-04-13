"""
Pokedex class that wraps pokebattler API
"""
import asyncio

import discord
from discord.ext import commands

from data import formats as F
from data import pokemon as DEX
from handlers.pokebattler import api_helper as AH
from handlers.pokebattler import pokebattler_api as API

class Pokedex():
    def __init__(self):
        self.update_pokemon_cache()
        self.update_moves_cache()
        self.update_raids_cache()
        self.update_rankings_cache()

    def update_pokemon_cache(self):
        self.pokemon = API.fetch_pokedex()

    def update_moves_cache(self):
        self.moves = API.fetch_moves()

    def update_raids_cache(self):
        self.raids = API.fetch_raids_filtered()

    def update_rankings_cache(self):
        self.rankings = API.fetch_rankings()

    def current_raid_bosses(self):
        current_raids = AH.get_raid_bosses()
        return current_raids

    def calculate_players_power_percent(self, player_level, boss_name):
        raid_data = self.raids.get(boss_name)

        name = raid_data.get("pokemon")
        tier = raid_data.get("tier")
        penalty = 1.5 if player_level < 40 else 1
        ranking = self.get_ranking(name, tier)
        if len(ranking) == 0:
            return 1/penalty

        shift_value = 4 - len(ranking)
        index = 0
        if player_level >= 45:
            index = 0
        elif player_level >= 40:
            index = 1
        elif player_level >= 30:
            index = 2
        else:
            index = 3
        index = index - shift_value

        if index < 0:
            return 1/penalty

        weight = 1/(penalty * ranking[index]) * 100

    def get_ranking(self, name, tier):
        pokemon_rankings = self.rankings.get(name)
        return pokemon_rankings.get(tier)

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

    def get_counter_for(self, bot, name, tier, weather):
        name_id = self.convert_name_to_id(name, tier)
        tier = tier.replace("T","")
        tier_id = f"RAID_LEVEL_{tier}".upper()
        weather_id = F.WEATHER_TO_POKEBATTLER.get(weather.lower())
        print(f"{name_id}, {tier_id}, {weather_id}")
        result, link = self.get_counter_data(name_id, tier_id, weather_id)
        link = link.replace("fight.", "www.")
        embed = discord.Embed(title=name.replace("-", " ").title(), description="Recommended counters and moves ", url=link)
        embed.add_field(name="Weather", value=F.WEATHER_TO_EMOJI.get(weather.lower()), inline=False)
        embed.add_field(name="Counters", value="With a **random moveset** and the above weather, here are the recommended counters.", inline=False)
        name_getter = AH.value_from_arg.get("name")
        counter = 1
        for pokemon in result:
            moves = pokemon.get("byMove")
            value = "\n".join([AH.move_to_readable(bot, movenum, move) for movenum,move in moves.items() if movenum == "move1" or movenum == "move2"])
            name = name_getter(pokemon)
            embed.add_field(name=f"{counter}) {name}", value=value, inline=True)
            counter += 1
        return embed

    def convert_name_to_id(self, name, tier):
        print(name, tier)
        spec_name = DEX.NAME_TO_POKEBATTLER_ID.get(name.title())
        if spec_name:
            return spec_name

        name = name.title()
        if name in DEX.MEGA_DEX.values():
            name = f"{name}_mega".upper()
            return name

        if name in DEX.ALOLAN_DEX.values():
            name = "_".join(name.split("-")[1:])
            name = f"{name}_alola_form".upper()
            return name

        if name in DEX.GALARIAN_DEX.values():
            name = "_".join(name.split("-")[1:])
            name = f"{name}_galarian_form".upper()
            return name

        if name in DEX.ALTERNATE_FORME_DEX.values():
            name = name.replace("-", "_")
            name = f"{name}_form".upper()
            return name

        name = name.replace("-","_").upper()
        return name
