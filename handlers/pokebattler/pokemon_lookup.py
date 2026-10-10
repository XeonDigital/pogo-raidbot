import re
import unicodedata

from fuzzywuzzy import fuzz, process

from handlers.pokebattler.pokemon_images import resolve_sprite_keys

REGION_PREFIXES = {
    "ALOLA": "Alolan", "ALOLAN": "Alolan",
    "GALAR": "Galarian", "GALARIAN": "Galarian",
    "HISUI": "Hisuian", "HISUIAN": "Hisuian",
    "PALDEA": "Paldean", "PALDEAN": "Paldean",
}

# Species names that cannot be derived from the pokebattler id.
# cheaper to put in code than table cuz the list is small and stable
DEFAULT_NAMES = {
    "NIDORAN_FEMALE": "Nidoran♀",
    "NIDORAN_MALE": "Nidoran♂",
    "FARFETCHD": "Farfetch'd",
    "SIRFETCHD": "Sirfetch'd",
    "MR_MIME": "Mr. Mime",
    "MR_RIME": "Mr. Rime",
    "MIME_JR": "Mime Jr.",
    "HO_OH": "Ho-Oh",
    "PORYGON_Z": "Porygon-Z",
    "TYPE_NULL": "Type: Null",
    "JANGMO_O": "Jangmo-o",
    "HAKAMO_O": "Hakamo-o",
    "KOMMO_O": "Kommo-o",
    "TAPU_KOKO": "Tapu-Koko",
    "TAPU_LELE": "Tapu-Lele",
    "TAPU_BULU": "Tapu-Bulu",
    "TAPU_FINI": "Tapu-Fini",
    "FLABEBE": "Flabébé",
}

_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_key(name):
    """Lowercase, strip accents/punctuation/spaces so ``Mr. Mime``, ``mr-mime`` and ``MR MIME`` agree."""
    name = str(name or "").replace("♀", "f").replace("♂", "m")
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub("", name.lower())


def _titled(tokens):
    return "-".join(token.title() for token in tokens)


def _species_display(species_id, names):
    return names.get(species_id) or " ".join(token.title() for token in species_id.split("_"))


def _split_species(tokens, species_ids):
    """Longest leading run of tokens that is itself a plain species id, e.g. MR_MIME in MR_MIME_GALARIAN."""
    for end in range(len(tokens), 0, -1):
        candidate = "_".join(tokens[:end])
        if candidate in species_ids:
            return candidate, tokens[end:]
    return tokens[0], tokens[1:]


# Shadow is shown in the image and the attack and def are calculated in real time -
# not stored in the db
_FOLDED_SUFFIXES = (("_SHADOW_FORM", "shadow"),)


def _folded(pokemon_id, ids):
    for suffix, tag in _FOLDED_SUFFIXES:
        if pokemon_id.endswith(suffix):
            base = pokemon_id.removesuffix(suffix)
            return tag, (f"{base}_FORM" if base not in ids and f"{base}_FORM" in ids else base)
    return None


def classify(pokemon_id, species_ids, names):
    tokens = pokemon_id.removesuffix("_FORM").split("_")

    if "MEGA" in tokens or tokens[-1] == "PRIMAL":
        split = tokens.index("MEGA") if "MEGA" in tokens else len(tokens) - 1
        name, extra = _species_display("_".join(tokens[:split]), names), tokens[split + 1:]
        return (f"{name}-{_titled(extra)}" if extra else name), ["mega"], None

    if tokens[-1] == "GIGANTAMAX":
        base = "_".join(tokens[:-1])
        name, _, _ = classify(base if base in species_ids else f"{base}_FORM", species_ids, names)
        return f"Gigantamax-{name}", ["gigantamax"], f"Gmax {name}"

    if pokemon_id in species_ids or not pokemon_id.endswith("_FORM"):
        return _species_display(pokemon_id, names), [], None

    species_id, qualifier = _split_species(tokens, species_ids)
    display = _species_display(species_id, names)
    if not qualifier:
        return display, [], None

    if qualifier[0] in REGION_PREFIXES:
        regional = f"{REGION_PREFIXES[qualifier[0]]}-{display.replace(' ', '-')}"
        variant = qualifier[1:]
        return (f"{regional}-{_titled(variant)}" if variant else regional), ["regional"], (regional if variant else None)

    alias = f"{' '.join(token.title() for token in qualifier)} {display}" if len("".join(qualifier)) > 1 else None
    return f"{display}-{_titled(qualifier)}", [], alias


def max_battle_bosses(payload, pokemon_list):
    """Species with a max battle in pokebattler's tier list."""
    ids = {p.get("pokemonId") for p in pokemon_list or []}
    species_by_id = {p.get("pokemonId"): (p.get("pokedex") or {}).get("pokemonId") for p in pokemon_list or []}
    species = set()
    for tier in (payload or {}).get("tiers") or []:
        if "_MAX" not in (tier.get("tier") or ""):
            continue
        for boss in tier.get("raids") or []:
            boss_id = boss.get("pokemon") or boss.get("pokemonId")
            if not boss_id:
                continue
            folded = _folded(boss_id, ids)
            base_id = folded[1] if folded else boss_id
            species.add(species_by_id.get(boss_id) or species_by_id.get(base_id) or base_id.removesuffix("_FORM"))
    return species


def _same_look_only(pokemon, base):
    # to put all costumes/forms when a mon is searched
    """A form that only changes looks (costumes, Unown letters, Vivillon patterns)"""
    if not base:
        return False
    return all(pokemon.get(key) == base.get(key) for key in ("type", "type2", "stats"))


def _strip_prefix(value, prefix):
    return value.removeprefix(prefix) if isinstance(value, str) else None


def build_entries(pokemon_list, names, max_battles=None, assets=None):
    """
    One dict per pokebattler ``pokemonId``, except shadow """
    pokemon_list = pokemon_list or []
    ids = {p.get("pokemonId") for p in pokemon_list if p.get("pokemonId")}
    species_ids = {i for i in ids if not i.endswith(("_FORM", "_GIGANTAMAX", "_PRIMAL")) and "_MEGA" not in i}
    folded = {}
    for pokemon_id in ids:
        if found := _folded(pokemon_id, ids):
            folded.setdefault(found[1], set()).add(found[0])
    max_species = max_battles or set()
    by_id = {p.get("pokemonId"): p for p in pokemon_list}
    # Dynamax applies to the whole evolution line
    family_of = {(p.get("pokedex") or {}).get("pokemonId") or p.get("pokemonId"): p.get("familyId") for p in pokemon_list}
    max_families = {family_of.get(species) or species for species in max_species}
    # A shadow anywhere in a non-legendary line makes the whole line shadow (shadows evolve into shadows).
    shadow_families = {by_id[base].get("familyId") for base, kinds in folded.items() if "shadow" in kinds and base in by_id}
    entries = []
    for pokemon in pokemon_list:
        pokemon_id = pokemon.get("pokemonId")
        pokedex = pokemon.get("pokedex") or {}
        dex_num = pokedex.get("pokemonNum")
        if not pokemon_id or not dex_num or _folded(pokemon_id, ids):
            continue
        display, tags, alias = classify(pokemon_id, species_ids, names)
        species_id = pokedex.get("pokemonId") or pokemon_id
        family = pokemon.get("familyId") or species_id
        extra = folded.get(pokemon_id, set())
        legendary = (by_id.get(species_id) or pokemon).get("rarity")  # legendary, mythic or ultra beast
        max_form = "mega" in tags or "gigantamax" in tags  # never shadow, and can't dynamax
        if not max_form and not legendary and family in shadow_families:
            extra.add("shadow")
        stats = pokemon.get("stats") or {}
        if pokemon_id != species_id and not tags and _same_look_only(pokemon, by_id.get(species_id)):
            extra.add("cosmetic")
        tags += sorted(extra)
        if family in max_families and not max_form:
            tags.append("dynamax")
        form = pokedex.get("form") or pokemon.get("form")
        icon_key, shiny_icon_key = resolve_sprite_keys(assets or {}, pokemon_id, species_id, int(dex_num), form)
        entries.append({
            "pokemon_id": pokemon_id,
            "species_id": species_id,
            "dex_num": int(dex_num),
            "display_name": display,
            "alias": alias,
            "icon_key": icon_key,
            "shiny_icon_key": shiny_icon_key,
            "sprites_known": assets is not None,
            "form": form,
            "parent_pokemon_id": pokemon.get("parentPokemonId"),
            "types": [t for t in (_strip_prefix(pokemon.get("type"), "POKEMON_TYPE_"),
                                  _strip_prefix(pokemon.get("type2"), "POKEMON_TYPE_")) if t],
            "tags": tags,
            "rarity": _strip_prefix(pokemon.get("rarity"), "POKEMON_RARITY_"),
            "max_battles_known": max_battles is not None,
            "base_attack": stats.get("baseAttack"),
            "base_defense": stats.get("baseDefense"),
            "base_stamina": stats.get("baseStamina"),
        })
    return entries


def species_rows(entries):
    """One ``pokemon_list`` row per species; the base form (``pokemon_id == species_id``) wins when present."""
    species = {}
    for entry in entries:
        current = species.get(entry["species_id"])
        if current is None or (entry["pokemon_id"] == entry["species_id"] and current["pokemon_id"] != entry["species_id"]):
            species[entry["species_id"]] = entry
    return [
        (species_id, e["dex_num"], e["rarity"])
        for species_id, e in species.items()
    ]


# The upserts never write ``overrides`` or manually added aliases, so hand edits survive every refresh.
UPSERT_POKEMON_LIST = """
INSERT INTO pokedex.pokemon_list(pokebattler_id, dex_num, rarity)
VALUES($1, $2, $3)
ON CONFLICT (pokebattler_id) DO UPDATE SET
  dex_num = EXCLUDED.dex_num, rarity = EXCLUDED.rarity, updated_at = now()
"""

UPSERT_POKEMON_FORMS = """
INSERT INTO pokedex.pokemon_forms(pokebattler_id, species_id, display_name, icon_key, form, parent_species_id,
                                  types, tags, aliases, shiny_icon_key)
SELECT $1::text, l.id, $3::text, $4::text, $5::text, parent.id, $7::text[], $8::text[],
       CASE WHEN $9::text IS NULL THEN '{}'::text[] ELSE ARRAY[$9::text] END, $11::text
FROM pokedex.pokemon_list l
LEFT JOIN pokedex.pokemon_list parent ON parent.pokebattler_id = $6::text
WHERE l.pokebattler_id = $2::text
ON CONFLICT (pokebattler_id) DO UPDATE SET
  species_id = EXCLUDED.species_id, display_name = EXCLUDED.display_name,
  icon_key = CASE WHEN $12::boolean THEN EXCLUDED.icon_key ELSE pokedex.pokemon_forms.icon_key END,
  shiny_icon_key = CASE WHEN $12::boolean THEN EXCLUDED.shiny_icon_key ELSE pokedex.pokemon_forms.shiny_icon_key END,
  form = EXCLUDED.form, parent_species_id = EXCLUDED.parent_species_id, types = EXCLUDED.types,
  updated_at = now(),
  tags = CASE WHEN $10::boolean THEN $8::text[]
              ELSE $8::text[] || ARRAY(SELECT t FROM unnest(pokedex.pokemon_forms.tags) AS t
                                       WHERE t = 'dynamax' AND t <> ALL($8::text[])) END,
  aliases = CASE WHEN $9::text IS NULL OR $9::text = ANY(pokedex.pokemon_forms.aliases)
                 THEN pokedex.pokemon_forms.aliases
                 ELSE array_append(pokedex.pokemon_forms.aliases, $9::text) END
"""

# $1 is the form's pokebattler id; it is swapped for the form's row id.
UPSERT_POKEMON_STATS = """
INSERT INTO pokedex.pokemon_stats(form_id, base_attack, base_defense, base_stamina)
SELECT f.id, $2::integer, $3::integer, $4::integer
FROM pokedex.pokemon_forms f
WHERE f.pokebattler_id = $1::text
ON CONFLICT (form_id) DO UPDATE SET
  base_attack = EXCLUDED.base_attack, base_defense = EXCLUDED.base_defense,
  base_stamina = EXCLUDED.base_stamina, updated_at = now()
"""


async def save_pokemon(database, entries):
    """Upsert species, forms (with their aliases) and base stats atomically (parents before children)."""
    form_rows = [(
        e["pokemon_id"], e["species_id"], e["display_name"], e["icon_key"], e["form"], e["parent_pokemon_id"],
        e["types"], e["tags"], e["alias"], e["max_battles_known"], e["shiny_icon_key"], e["sprites_known"],
    ) for e in entries]
    stats_rows = [
        (e["pokemon_id"], e["base_attack"], e["base_defense"], e["base_stamina"])
        for e in entries
        if None not in (e["base_attack"], e["base_defense"], e["base_stamina"])
    ]
    async with database.connect() as conn:
        async with conn.transaction():
            await conn.executemany(UPSERT_POKEMON_LIST, species_rows(entries))
            await conn.executemany(UPSERT_POKEMON_FORMS, form_rows)
            await conn.executemany(UPSERT_POKEMON_STATS, stats_rows)
    return len(form_rows)


LOAD_POKEMON = """
SELECT pokebattler_id AS pokemon_id,
       COALESCE(overrides->>'display_name', display_name) AS display_name,
       COALESCE(overrides->>'icon_key', icon_key) AS icon_key,
       COALESCE(overrides->>'shiny_icon_key', shiny_icon_key) AS shiny_icon_key,
       'mega' = ANY(tags) AS is_mega,
       aliases
FROM pokedex.pokemon_forms
ORDER BY pokebattler_id
"""

# is_mega -> {normalized name, id or alias: row}, rebuilt by ``load_cache``.
_index = {}


def _build_index(rows):
    """Where two rows share a spelling, a display name beats an id and an id beats an alias."""
    index = {}
    spellings_of = (
        lambda row: [row["display_name"]],
        lambda row: [row["pokemon_id"].removesuffix("_FORM")],
        lambda row: row["aliases"],
    )
    for spellings in spellings_of:
        for row in rows:
            bucket = index.setdefault(row["is_mega"], {})
            for spelling in spellings(row):
                bucket.setdefault(normalize_key(spelling), row)
    return index


async def load_cache(database):
    """Replace the in-memory lookup with what is currently in the database."""
    global _index
    _index = _build_index([dict(row) for row in await database.fetch(LOAD_POKEMON)])


# Fuzzy score (0-100, ``fuzz.ratio``) needed to offer "Did you mean ...?".
SUGGEST_MIN_RATIO = 75


def find_pokemon(name, *, mega=False):
    """Exact lookup (name, id or alias, ignoring case and punctuation)"""
    return _index.get(mega, {}).get(normalize_key(name))


def suggest_pokemon(name, *, mega=False):
    """Display name of the closest spelling if it is similar enough to be a plausible typo, else None."""
    bucket = _index.get(mega, {})
    match = process.extractOne(normalize_key(name), list(bucket), scorer=fuzz.ratio, score_cutoff=SUGGEST_MIN_RATIO)
    return bucket[match[0]]["display_name"] if match else None
