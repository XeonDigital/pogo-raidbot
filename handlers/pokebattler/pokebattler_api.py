import json
import requests

from cachecontrol import CacheControl
from cachecontrol.caches import FileCache
import discord

import handlers.pokebattler.api_helper as AH

def retrieve_data_from_api(link, params):
    sess = CacheControl(requests.Session(),
                        cache=FileCache('.webcache'))
    if params:
        sess.params = params
    session = sess.get(link)
    return session.json(), session.url

def fetch_pokedex():
    data, _ = retrieve_data_from_api("https://fight.pokebattler.com/pokemon", None)
    return data['pokemon']

def fetch_raids():
    data, _ = retrieve_data_from_api("https://fight.pokebattler.com/raids", None)
    return data

def fetch_moves():
    data, _ = retrieve_data_from_api("https://fight.pokebattler.com/moves", None)
    return data['move']

valid_tiers = [
    "RAID_LEVEL_1",
    "RAID_LEVEL_3",
    "RAID_LEVEL_5",
    "RAID_LEVEL_6",
    "RAID_LEVEL_MEGA",
    "RAID_LEVEL_MEGA_5",
    "RAID_LEVEL_ELITE",
    "RAID_LEVEL_1_SHADOW",
    "RAID_LEVEL_3_SHADOW",
    "RAID_LEVEL_5_SHADOW",
    "RAID_LEVEL_ULTRA_BEAST"
]
def current_tier_valid(tier):
    return tier in valid_tiers

def add_tier_to_raid_data(raid, tier):
    raid = dict(raid or {})
    raid["tier"] = tier
    return raid

def filter_current_raids(raids):
    grouped = {}
    for tier in (raids or {}).get("tiers") or []:
        tier_id = tier.get("tier")
        if not current_tier_valid(tier_id):
            continue
        for raid in tier.get("raids") or []:
            pokemon = raid.get("pokemon")
            if not pokemon:
                continue
            name = AH.format_pokemon_name(pokemon)
            if not name:
                continue
            grouped.setdefault(name, []).append(add_tier_to_raid_data(raid, tier_id))
    return grouped

def fetch_raids_filtered():
    return filter_current_raids(fetch_raids())

def summarize_raids(raw_raids):
    """
    Build a compact summary of the /raids payload.
    Returns: list[tuple[str, int]] of (tier_id, raid_count) sorted by tier_id.
    """
    tiers = raw_raids.get("tiers") or []
    summary = []
    for tier in tiers:
        tier_id = tier.get("tier")
        raids = tier.get("raids") or []
        summary.append((tier_id, len(raids)))
    summary.sort(key=lambda x: (x[0] or ""))
    return summary

def link_builder(name, tier, weather):
    return f"https://fight.pokebattler.com/raids/defenders/{name}/levels/{tier}/attackers/levels/40/strategies/CINEMATIC_ATTACK_WHEN_POSSIBLE/DEFENSE_RANDOM_MC"
