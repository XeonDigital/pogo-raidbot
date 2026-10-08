import re
import unicodedata

from fuzzywuzzy import fuzz, process

from data import pokemon as DEX

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


def classify(pokemon_id, species_ids, names):
    flags = dict.fromkeys(("is_mega", "is_shadow", "is_gigantamax", "is_cosmetic"), False)

    # Shadow and gigantamax rows are named after their base form.
    for suffix, flag, prefix in (("_SHADOW_FORM", "is_shadow", "Shadow"), ("_GIGANTAMAX", "is_gigantamax", "Gigantamax")):
        if pokemon_id.endswith(suffix):
            base = pokemon_id.removesuffix(suffix)
            flags[flag] = True
            base_name = classify(base if base in species_ids else f"{base}_FORM", species_ids, names)[0]
            return f"{prefix} {base_name}", flags, None

    tokens = pokemon_id.removesuffix("_FORM").split("_")

    if "MEGA" in tokens or tokens[-1] == "PRIMAL":
        flags["is_mega"] = True
        split = tokens.index("MEGA") if "MEGA" in tokens else len(tokens) - 1
        name, extra = _species_display("_".join(tokens[:split]), names), tokens[split + 1:]
        return (f"{name}-{_titled(extra)}" if extra else name), flags, None

    if pokemon_id in species_ids or not pokemon_id.endswith("_FORM"):
        return _species_display(pokemon_id, names), flags, None

    species_id, qualifier = _split_species(tokens, species_ids)
    display = _species_display(species_id, names)
    if not qualifier:
        flags["is_cosmetic"] = True
        return display, flags, None

    if qualifier[0] in REGION_PREFIXES:
        regional = f"{REGION_PREFIXES[qualifier[0]]}-{display.replace(' ', '-')}"
        variant = qualifier[1:]
        return (f"{regional}-{_titled(variant)}" if variant else regional), flags, (regional if variant else None)

    flags["is_cosmetic"] = (
        any(re.search(r"\d", token) for token in qualifier)
        or (len(qualifier) == 1 and len(qualifier[0]) == 1)
    )
    alias = None if flags["is_cosmetic"] else f"{' '.join(token.title() for token in qualifier)} {display}"
    return f"{display}-{_titled(qualifier)}", flags, alias


def max_species_from_raids(raw_raids, pokemon_list):
    """Species that appear in raids"""
    species_by_id = {p.get("pokemonId"): (p.get("pokedex") or {}).get("pokemonId") for p in pokemon_list or []}
    found = set()
    for tier in (raw_raids or {}).get("tiers") or []:
        if "_MAX" not in (tier.get("tier") or ""):
            continue
        for raid in tier.get("raids") or []:
            raid_id = raid.get("pokemon") or raid.get("pokemonId")
            if raid_id:
                found.add(species_by_id.get(raid_id) or raid_id.removesuffix("_GIGANTAMAX").removesuffix("_FORM"))
    return found

# To be removed once we find a dynamic ones
def _icon_keys(*sources):
    """``{normalized name: thumbnail key}`` from the static lists; the first source wins on a collision."""
    keys = {}
    for source in sources:
        for icon_key, display in source.items():
            keys.setdefault(normalize_key(display), icon_key)
    return keys


# Thumbnail keys (``0025_00``, ``003_51``) only exist in the static lists; they are read at ingest only.
_STATIC_ICONS = _icon_keys(DEX.NATIONAL_DEX, DEX.GALARIAN_DEX, DEX.ALOLAN_DEX, DEX.ALTERNATE_FORME_DEX)
_STATIC_MEGA_ICONS = _icon_keys(DEX.MEGA_DEX)


def _strip_prefix(value, prefix):
    return value.removeprefix(prefix) if isinstance(value, str) else None


async def load_names(database):
    rows = await database.fetch("SELECT pokebattler_id, name_override FROM pokedex.pokemon_list WHERE name_override IS NOT NULL")
    return {**DEFAULT_NAMES, **{row["pokebattler_id"]: row["name_override"] for row in rows}}


def build_entries(pokemon_list, names, max_species=None):
    """
    One dict per pokebattler ``pokemonId``. ``max_species`` is the set from ``max_species_from_raids``
    """
    pokemon_list = pokemon_list or []
    ids = {p.get("pokemonId") for p in pokemon_list if p.get("pokemonId")}
    species_ids = {i for i in ids if not i.endswith(("_FORM", "_GIGANTAMAX", "_PRIMAL")) and "_MEGA" not in i}
    entries = []
    for pokemon in pokemon_list:
        pokemon_id = pokemon.get("pokemonId")
        pokedex = pokemon.get("pokedex") or {}
        dex_num = pokedex.get("pokemonNum")
        if not pokemon_id or not dex_num:
            continue
        display, flags, alias = classify(pokemon_id, species_ids, names)
        species_id = pokedex.get("pokemonId") or pokemon_id
        stats = pokemon.get("stats") or {}
        icons = _STATIC_MEGA_ICONS if flags["is_mega"] else _STATIC_ICONS
        entries.append({
            "pokemon_id": pokemon_id,
            "species_id": species_id,
            "dex_num": int(dex_num),
            "display_name": display,
            "species_display": _species_display(species_id, names),
            "alias": alias,
            "icon_key": icons.get(normalize_key(display)) or f"{int(dex_num):03d}_00",
            "form": pokedex.get("form") or pokemon.get("form"),
            "family_id": pokemon.get("familyId"),
            "parent_pokemon_id": pokemon.get("parentPokemonId"),
            "type_1": _strip_prefix(pokemon.get("type"), "POKEMON_TYPE_"),
            "type_2": _strip_prefix(pokemon.get("type2"), "POKEMON_TYPE_"),
            "rarity": _strip_prefix(pokemon.get("rarity"), "POKEMON_RARITY_"),
            **flags,
            "can_dynamax": None if max_species is None else species_id in max_species,
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
        (species_id, e["dex_num"], e["species_display"], e["family_id"], e["rarity"], e["can_dynamax"])
        for species_id, e in species.items()
    ]


# The upserts never write ``overrides`` or manually added aliases, so hand edits survive every refresh.
UPSERT_POKEMON_LIST = """
INSERT INTO pokedex.pokemon_list(pokebattler_id, dex_num, display_name, family_id, rarity, can_dynamax)
VALUES($1, $2, $3, $4, $5, COALESCE($6::boolean, FALSE))
ON CONFLICT (pokebattler_id) DO UPDATE SET
  dex_num = EXCLUDED.dex_num, display_name = EXCLUDED.display_name, family_id = EXCLUDED.family_id,
  rarity = EXCLUDED.rarity, can_dynamax = COALESCE($6::boolean, pokedex.pokemon_list.can_dynamax),
  updated_at = now()
"""

# $2 and $6 are pokebattler ids (the species, and the species it evolves from); they are swapped for row ids.
UPSERT_POKEMON_FORMS = """
INSERT INTO pokedex.pokemon_forms(pokebattler_id, species_id, display_name, icon_key, form, parent_species_id,
                                  type_1, type_2, is_mega, is_shadow, is_gigantamax, is_cosmetic, aliases)
SELECT $1::text, l.id, $3::text, $4::text, $5::text, parent.id, $7::text, $8::text,
       $9::boolean, $10::boolean, $11::boolean, $12::boolean,
       CASE WHEN $13::text IS NULL THEN '{}'::text[] ELSE ARRAY[$13::text] END
FROM pokedex.pokemon_list l
LEFT JOIN pokedex.pokemon_list parent ON parent.pokebattler_id = $6::text
WHERE l.pokebattler_id = $2::text
ON CONFLICT (pokebattler_id) DO UPDATE SET
  species_id = EXCLUDED.species_id, display_name = EXCLUDED.display_name, icon_key = EXCLUDED.icon_key,
  form = EXCLUDED.form, parent_species_id = EXCLUDED.parent_species_id, type_1 = EXCLUDED.type_1,
  type_2 = EXCLUDED.type_2, is_mega = EXCLUDED.is_mega, is_shadow = EXCLUDED.is_shadow,
  is_gigantamax = EXCLUDED.is_gigantamax, is_cosmetic = EXCLUDED.is_cosmetic, updated_at = now(),
  aliases = CASE WHEN $13::text IS NULL OR $13::text = ANY(pokedex.pokemon_forms.aliases)
                 THEN pokedex.pokemon_forms.aliases
                 ELSE array_append(pokedex.pokemon_forms.aliases, $13::text) END
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
        e["type_1"], e["type_2"], e["is_mega"], e["is_shadow"], e["is_gigantamax"], e["is_cosmetic"],
        e["alias"],
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
       is_mega,
       COALESCE((overrides->>'is_cosmetic')::boolean, is_cosmetic) AS is_cosmetic,
       aliases
FROM pokedex.pokemon_forms
WHERE NOT is_shadow AND NOT is_gigantamax
ORDER BY pokebattler_id
"""

# (is_mega, is_cosmetic) -> {normalized name, id or alias: row}, rebuilt by ``load_cache``.
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
            bucket = index.setdefault((row["is_mega"], row["is_cosmetic"]), {})
            for spelling in spellings(row):
                bucket.setdefault(normalize_key(spelling), row)
    return index


async def load_cache(database):
    """Replace the in-memory lookup with what is currently in the database."""
    global _index
    _index = _build_index([dict(row) for row in await database.fetch(LOAD_POKEMON)])


# Fuzzy score (0-100, ``fuzz.ratio``) needed to offer "Did you mean ...?".
SUGGEST_MIN_RATIO = 75


def find_pokemon(name, *, mega=False, costumes=False):
    """Exact lookup (name, id or alias, ignoring case and punctuation). Row has pokemon_id, display_name, icon_key."""
    return _index.get((mega, costumes), {}).get(normalize_key(name))


def suggest_pokemon(name, *, mega=False):
    """Display name of the closest spelling if it is similar enough to be a plausible typo, else None."""
    bucket = _index.get((mega, False), {})
    match = process.extractOne(normalize_key(name), list(bucket), scorer=fuzz.ratio, score_cutoff=SUGGEST_MIN_RATIO)
    return bucket[match[0]]["display_name"] if match else None
