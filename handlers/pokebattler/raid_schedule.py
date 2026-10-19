import asyncio
import datetime as dt

import discord

from classes.components import EmbedPages
from handlers.pokebattler import api_helper as AH
from handlers.pokebattler import pokebattler_api as API
from handlers.pokebattler.pokemon_images import image_url
from handlers.pokebattler.pokemon_lookup import display_pokemon

WEEK_TITLES = ("This week", "Next week")

# Rotations change on Wednesday. Pokebattler's dates are local times, read here as UTC: a rotation runs from
# 13:00 Wed to about 05:00 the next Wed, so weeks split at 10:00 and end dates are pulled back 12h for display.
# TODO: the split happens at 10:00 UTC for everyone, so "This week" flips early or late depending on the user's
# timezone, and only dates are shown. Enhancement: show times with Discord timestamps (<t:...>)
ROTATION_WEEKDAY = 2
ROTATION_HOUR = 10
DAY = dt.timedelta(days=1)
END_DATE_SHIFT = dt.timedelta(hours=12)

# In display order.
TIER_LABELS = {
    "RAID_LEVEL_5": "Tier 5",
    "RAID_LEVEL_ULTRA_BEAST": "Ultra Beast",
    "RAID_LEVEL_ELITE": "Elite",
    "RAID_LEVEL_MEGA_5": "Mega Legendary",
    "RAID_LEVEL_MEGA": "Mega",
    "RAID_LEVEL_5_SHADOW": "Shadow Tier 5",
    "RAID_LEVEL_3_SHADOW": "Shadow Tier 3",
    "RAID_LEVEL_3": "Tier 3",
    "RAID_LEVEL_1": "Tier 1",
    "RAID_LEVEL_1_SHADOW": "Shadow Tier 1",
    "RAID_LEVEL_6_MAX": "Gigantamax",
    "RAID_LEVEL_5_MAX": "Legendary Max Battle",
    "RAID_LEVEL_4_MAX": "Max Battle ★4",
    "RAID_LEVEL_3_MAX": "Max Battle ★3",
    "RAID_LEVEL_2_MAX": "Max Battle ★2",
    "RAID_LEVEL_1_MAX": "Max Battle ★1",
}
TIER_ORDER = list(TIER_LABELS)

# Bosses that need a group get counters. Max battles use a different simulation, so they are only listed.
COUNTER_TIERS = {
    "RAID_LEVEL_5", "RAID_LEVEL_ULTRA_BEAST", "RAID_LEVEL_ELITE", "RAID_LEVEL_MEGA_5", "RAID_LEVEL_MEGA",
    "RAID_LEVEL_5_SHADOW", "RAID_LEVEL_3_SHADOW",
}
COUNTER_WEATHER = "NO_WEATHER"

# Discord's embed caps. Bosses get one field per tier, so a busy week (Road of Legends) can't hit the field cap.
FIELD_LIMIT = 1024
FIELD_COUNT_LIMIT = 25
EMBED_LIMIT = 6000
MOST_COUNTERS = 5


def tier_label(tier):
    return TIER_LABELS.get(tier) or tier.removeprefix("RAID_LEVEL_").replace("_", " ").title()


def tier_rank(tier):
    return TIER_ORDER.index(tier) if tier in TIER_LABELS else len(TIER_ORDER)


def week_windows(now, weeks=len(WEEK_TITLES)):
    """[(start, end)] for this week and the ones after it."""
    start = now.replace(hour=ROTATION_HOUR, minute=0, second=0, microsecond=0)
    start -= DAY * ((now.weekday() - ROTATION_WEEKDAY) % 7)
    if start > now:
        start -= 7 * DAY
    return [(start + 7 * DAY * i, start + 7 * DAY * (i + 1)) for i in range(weeks)]


def when(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)


def entries_in(schedule, start, end):
    """One schedule entry per boss, tier and costume running during [start, end), in display order."""
    first = {}
    for entry in sorted(schedule or [], key=lambda e: e["startDate"]):
        if when(entry["startDate"]) < end and when(entry["endDate"]) > start:
            # Costumed bosses share the plain boss's id and are only told apart by the costume flag.
            first.setdefault((entry["pokemon"], entry["tier"], bool(entry.get("costume"))), entry)
    return sorted(first.values(), key=lambda e: (tier_rank(e["tier"]), e["startDate"], e["pokemon"]))


def day_range(start, end):
    first, last = (f"{day:%a %b} {day.day}" for day in (start, end - END_DATE_SHIFT))
    return first if first == last else f"{first} – {last}"


def dates_note(entry, start, end):
    """The boss's own dates when it is only up for part of the week."""
    entry_start, entry_end = when(entry["startDate"]), when(entry["endDate"])
    if entry_start > start + DAY or entry_end < end - DAY:
        return day_range(entry_start, entry_end)
    return None


def boss_name(entry):
    name, row = display_pokemon(entry["pokemon"])
    return (f"{name} (Costume)" if entry.get("costume") else name), row


def counter_text(name, counters, note, emojis, shown):
    """A boss's name followed by its top ``shown`` counters."""
    lines = [f"__**{name}**__" + (f" · _{note} only_" if note else "")]
    if shown and not counters:
        lines.append("Counters unavailable right now.")
    for rank, counter in enumerate((counters or [])[:shown], start=1):
        counter_name, _ = display_pokemon(counter["pokemonId"])
        lines.append(f"**{rank}.** {counter_name} — {' · '.join(AH.counter_moves(counter, emojis))}")
    return "\n".join(lines)


def fits(embed):
    return (len(embed) <= EMBED_LIMIT and len(embed.fields) <= FIELD_COUNT_LIMIT
            and all(len(field.value) <= FIELD_LIMIT for field in embed.fields))


def tier_value(bosses, emojis, max_counters):
    """One field's worth of [(name, counters, note)], with as many counters (up to ``max_counters``) as fit in it."""
    for shown in range(max_counters, -1, -1):
        value = ("\n\n" if shown else "\n").join(counter_text(*boss, emojis, shown) for boss in bosses)
        if len(value) <= FIELD_LIMIT:
            break
    return value[:FIELD_LIMIT]


def build_week_embed(title, window, entries, counters, emojis):
    # Tiers with several bosses (Road of Legends) show fewer counters per boss to fit their field, and busy weeks
    # show fewer everywhere until the whole embed fits Discord's limits.
    for shown in range(MOST_COUNTERS, -1, -1):
        embed = week_embed(title, window, entries, counters, emojis, shown)
        if fits(embed):
            break
    return embed


def week_embed(title, window, entries, counters, emojis, shown):
    start, end = window
    embed = discord.Embed(title=f"Raid Rotation · {title}", url="https://www.pokebattler.com/raids",
                          description=day_range(start, end))
    embed.set_footer(text="Counters from Pokebattler: level 40 attackers, random boss moves, no weather")
    if not entries:
        embed.description += "\n\nPokebattler hasn't posted the raids for this week yet."
        return embed

    group, listed = {}, {}
    for entry in entries:
        name, row = boss_name(entry)
        note = dates_note(entry, start, end)
        label = tier_label(entry["tier"])
        if entry["tier"] in COUNTER_TIERS:
            if row and not embed.thumbnail.url:
                embed.set_thumbnail(url=image_url(row["icon_key"]))
            boss_counters = counters.get((entry["pokemon"], entry["tier"]))
            group.setdefault(label, []).append((name, boss_counters, note))
        else:
            listed.setdefault(label, []).append(f"{name} ({note})" if note else name)
    for label, bosses in group.items():
        embed.add_field(name=label, value=tier_value(bosses, emojis, shown), inline=False)
    for label, names in listed.items():
        embed.add_field(name=label, value="\n".join(names), inline=True)
    return embed


async def fetch_counters(dex, pokemon_id, tier):
    """Top counters for a boss (cached by pokebattler's own headers), or None if it can't be reached."""
    try:
        counters, _ = await asyncio.to_thread(dex.get_counter_data, pokemon_id, tier, COUNTER_WEATHER)
        return counters
    except Exception as error:
        print(f"[!] Could not fetch counters for {pokemon_id} ({tier}): {type(error).__name__}: {error}")
        return None


async def send_weekly_raids(bot, interaction: discord.Interaction):
    try:
        payload = await asyncio.to_thread(API.fetch_raids)
    except Exception as error:
        await interaction.followup.send(f"Couldn't reach Pokebattler (`{type(error).__name__}`).", ephemeral=True)
        return

    windows = week_windows(dt.datetime.now(dt.timezone.utc))
    weeks = [entries_in(payload.get("breakingNews"), *window) for window in windows]
    bosses = list({(e["pokemon"], e["tier"]) for week in weeks for e in week if e["tier"] in COUNTER_TIERS})
    counters = dict(zip(bosses, await asyncio.gather(*(fetch_counters(bot.dex, *boss) for boss in bosses))))

    embeds = [build_week_embed(title, window, entries, counters, AH.TYPE_EMOJIS)
              for title, window, entries in zip(WEEK_TITLES, windows, weeks)]
    await EmbedPages(embeds).send(interaction)
