from types import SimpleNamespace

import pytest

from classes.pokedex import Pokedex
from handlers.pokebattler import pokemon_lookup as lookup
from handlers.pokebattler.api_helper import format_pokemon_name
from handlers.pokebattler.pokemon_images import image_url
from handlers.pokebattler.pokemon_lookup import (
    DEFAULT_NAMES,
    _build_index,
    _folded,
    build_entries,
    classify,
    find_pokemon,
    max_battle_bosses,
    normalize_key,
    species_rows,
    suggest_pokemon,
)
from handlers.pokebattler.pokebattler_api import filter_current_raids
from pogo_raid_lib import (
    normalize_shadow_pokemon_name_for_lookup,
    validate_and_format_message,
    validate_invites_argument,
    validate_pokemon,
    validate_tier,
    validate_weather_argument,
)


SPECIES_IDS = {
    "MEWTWO",
    "NIDORAN_FEMALE",
    "MR_MIME",
    "NINETALES",
    "CHARIZARD",
    "CHARMANDER",
    "VENUSAUR",
    "BULBASAUR",
    "RATTATA",
    "ZORUA",
    "WOOPER",
    "LANDORUS",
    "PIKACHU",
    "GENGAR",
    "SABLEYE",
    "SQUIRTLE",
    "FALINKS",
    "LAPRAS",
}


def pokebattler_mon(pokemon_id, dex_num, species=None, family=None, rarity=None,
                    type_="NORMAL", type2=None, stats=None, form=None):
    species = species or pokemon_id
    return {
        "pokemonId": pokemon_id,
        "pokedex": {"pokemonId": species, "pokemonNum": dex_num, "form": form},
        "familyId": family or species,
        "rarity": rarity,
        "type": f"POKEMON_TYPE_{type_}" if type_ else None,
        "type2": f"POKEMON_TYPE_{type2}" if type2 else None,
        "stats": stats or {"baseAttack": 1, "baseDefense": 1, "baseStamina": 1},
    }


def entries_by_id(entries):
    return {entry["pokemon_id"]: entry for entry in entries}


@pytest.fixture
def pokemon_index():
    rows = [
        {
            "pokemon_id": "MEWTWO",
            "display_name": "Mewtwo",
            "icon_key": "go:pm150",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": [],
        },
        {
            "pokemon_id": "MR_MIME",
            "display_name": "Mr. Mime",
            "icon_key": "go:pm122",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": [],
        },
        {
            "pokemon_id": "NINETALES_ALOLA_FORM",
            "display_name": "Alolan-Ninetales",
            "icon_key": "go:pm38",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": [],
        },
        {
            "pokemon_id": "CHARIZARD_MEGA_X",
            "display_name": "Charizard-X",
            "icon_key": "go:pm6",
            "shiny_icon_key": None,
            "is_mega": True,
            "aliases": [],
        },
        {
            "pokemon_id": "VENUSAUR_GIGANTAMAX",
            "display_name": "Gigantamax-Venusaur",
            "icon_key": "go:pm3",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Gmax Venusaur"],
        },
        {
            "pokemon_id": "PIKACHU",
            "display_name": "Pikachu",
            "icon_key": "go:pm25",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": [],
        },
        {
            "pokemon_id": "PIKACHU_POP_STAR_FORM",
            "display_name": "Pikachu-Pop-Star",
            "icon_key": "go:pm25",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Pop Star Pikachu"],
        },
        {
            "pokemon_id": "PIKACHU_DOCTOR_FORM",
            "display_name": "Pikachu-Doctor",
            "icon_key": "go:pm25",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Doctor Pikachu"],
        },
        {
            "pokemon_id": "PIKACHU_ADVENTURE_HAT_2020_FORM",
            "display_name": "Pikachu-Adventure-Hat-2020",
            "icon_key": "go:pm25",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Adventure Hat 2020 Pikachu"],
        },
        {
            "pokemon_id": "GENGAR_COSTUME_2020_FORM",
            "display_name": "Gengar-Costume-2020",
            "icon_key": "go:pm94",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Costume 2020 Gengar"],
        },
        {
            "pokemon_id": "SQUIRTLE_FALL_2019_FORM",
            "display_name": "Squirtle-Fall-2019",
            "icon_key": "go:pm7",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Fall 2019 Squirtle"],
        },
        {
            "pokemon_id": "FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM",
            "display_name": "Falinks-Gofest-2025-Train-Conductor",
            "icon_key": "go:pm870",
            "shiny_icon_key": None,
            "is_mega": False,
            "aliases": ["Gofest 2025 Train Conductor Falinks"],
        },
    ]
    previous = lookup._index
    lookup._index = _build_index(rows)
    try:
        yield
    finally:
        lookup._index = previous


def make_dex(raids):
    dex = Pokedex.__new__(Pokedex)
    dex.raids = raids
    return dex


def test_normalize_key_treats_punctuation_as_the_same_name():
    assert normalize_key("Mr. Mime") == normalize_key("mr-mime") == normalize_key("MR MIME")
    assert normalize_key("Nidoran♀") == normalize_key("nidoranf")


def test_classify_base_species_and_special_names():
    assert classify("MEWTWO", SPECIES_IDS, {}) == ("Mewtwo", [], None)
    assert classify("NIDORAN_FEMALE", SPECIES_IDS, DEFAULT_NAMES) == ("Nidoran♀", [], None)


def test_classify_mega_and_primal():
    assert classify("CHARIZARD_MEGA_X", SPECIES_IDS, {}) == ("Charizard-X", ["mega"], None)
    assert classify("GROUDON_PRIMAL", SPECIES_IDS | {"GROUDON"}, {}) == ("Groudon", ["mega"], None)


def test_classify_gigantamax_and_regional():
    assert classify("VENUSAUR_GIGANTAMAX", SPECIES_IDS, {}) == (
        "Gigantamax-Venusaur",
        ["gigantamax"],
        "Gmax Venusaur",
    )
    assert classify("NINETALES_ALOLA_FORM", SPECIES_IDS, {}) == (
        "Alolan-Ninetales",
        ["regional"],
        None,
    )
    assert classify("MR_MIME_GALARIAN_FORM", SPECIES_IDS, DEFAULT_NAMES) == (
        "Galarian-Mr.-Mime",
        ["regional"],
        None,
    )
    assert classify("ZORUA_HISUIAN_FORM", SPECIES_IDS, {}) == (
        "Hisuian-Zorua",
        ["regional"],
        None,
    )
    assert classify("WOOPER_PALDEA_FORM", SPECIES_IDS, {}) == (
        "Paldean-Wooper",
        ["regional"],
        None,
    )
    assert classify("NINETALES_ALOLA_HAT_FORM", SPECIES_IDS, {}) == (
        "Alolan-Ninetales-Hat",
        ["regional"],
        "Alolan-Ninetales",
    )
    assert classify("LANDORUS_THERIAN_FORM", SPECIES_IDS, {}) == (
        "Landorus-Therian",
        [],
        "Therian Landorus",
    )


def test_classify_costume_forms():
    assert classify("PIKACHU_POP_STAR_FORM", SPECIES_IDS, {}) == (
        "Pikachu-Pop-Star",
        [],
        "Pop Star Pikachu",
    )
    assert classify("PIKACHU_ROCK_STAR_FORM", SPECIES_IDS, {}) == (
        "Pikachu-Rock-Star",
        [],
        "Rock Star Pikachu",
    )
    assert classify("PIKACHU_DOCTOR_FORM", SPECIES_IDS, {}) == (
        "Pikachu-Doctor",
        [],
        "Doctor Pikachu",
    )
    assert classify("PIKACHU_ADVENTURE_HAT_2020_FORM", SPECIES_IDS, {}) == (
        "Pikachu-Adventure-Hat-2020",
        [],
        "Adventure Hat 2020 Pikachu",
    )
    assert classify("PIKACHU_FALL_2019_FORM", SPECIES_IDS, {}) == (
        "Pikachu-Fall-2019",
        [],
        "Fall 2019 Pikachu",
    )
    assert classify("SQUIRTLE_FALL_2019_FORM", SPECIES_IDS, {}) == (
        "Squirtle-Fall-2019",
        [],
        "Fall 2019 Squirtle",
    )
    assert classify("CHARMANDER_FALL_2019_FORM", SPECIES_IDS, {}) == (
        "Charmander-Fall-2019",
        [],
        "Fall 2019 Charmander",
    )
    assert classify("BULBASAUR_FALL_2019_FORM", SPECIES_IDS, {}) == (
        "Bulbasaur-Fall-2019",
        [],
        "Fall 2019 Bulbasaur",
    )
    assert classify("GENGAR_COSTUME_2020_FORM", SPECIES_IDS, {}) == (
        "Gengar-Costume-2020",
        [],
        "Costume 2020 Gengar",
    )
    assert classify("SABLEYE_COSTUME_2020_FORM", SPECIES_IDS, {}) == (
        "Sableye-Costume-2020",
        [],
        "Costume 2020 Sableye",
    )
    assert classify("LAPRAS_COSTUME_2020_FORM", SPECIES_IDS, {}) == (
        "Lapras-Costume-2020",
        [],
        "Costume 2020 Lapras",
    )
    assert classify("FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM", SPECIES_IDS, {}) == (
        "Falinks-Gofest-2025-Train-Conductor",
        [],
        "Gofest 2025 Train Conductor Falinks",
    )


def test_folded_shadow_maps_to_base_or_form_id():
    assert _folded("MEWTWO_SHADOW_FORM", {"MEWTWO", "MEWTWO_SHADOW_FORM"}) == ("shadow", "MEWTWO")
    assert _folded("RATTATA_ALOLA_SHADOW_FORM", {"RATTATA_ALOLA_FORM", "RATTATA_ALOLA_SHADOW_FORM"}) == (
        "shadow",
        "RATTATA_ALOLA_FORM",
    )
    assert _folded("MEWTWO", {"MEWTWO"}) is None


def test_max_battle_bosses_only_counts_max_tiers():
    pokemon_list = [
        pokebattler_mon("WOOLOO", 831),
        pokebattler_mon("CHARIZARD", 6),
        pokebattler_mon("MEWTWO", 150, rarity="POKEMON_RARITY_LEGENDARY"),
    ]
    payload = {
        "tiers": [
            {"tier": "RAID_LEVEL_5", "raids": [{"pokemon": "MEWTWO"}]},
            {"tier": "RAID_LEVEL_1_MAX", "raids": [{"pokemon": "WOOLOO"}]},
            {"tier": "RAID_LEVEL_3_MAX", "raids": [{"pokemonId": "CHARIZARD"}]},
        ]
    }
    bosses = max_battle_bosses(payload, pokemon_list)
    assert "WOOLOO" in bosses
    assert "CHARIZARD" in bosses
    assert "MEWTWO" not in bosses
    assert not max_battle_bosses(None, pokemon_list)
    assert not max_battle_bosses({"tiers": []}, None)


def test_build_entries_skips_shadow_rows_and_tags_families():
    stats = {"baseAttack": 10, "baseDefense": 10, "baseStamina": 10}
    costume_stats = dict(stats)
    different_stats = {"baseAttack": 99, "baseDefense": 10, "baseStamina": 10}
    pokemon_list = [
        pokebattler_mon("RATTATA", 19, stats=stats),
        pokebattler_mon("RATTATA_SHADOW_FORM", 19, species="RATTATA", family="RATTATA", stats=stats),
        pokebattler_mon("RATTATA_SANTA_HAT_FORM", 19, species="RATTATA", family="RATTATA",
                        form="RATTATA_SANTA_HAT_FORM", stats=costume_stats),
        pokebattler_mon("RATTATA_ARMORED_FORM", 19, species="RATTATA", family="RATTATA",
                        form="RATTATA_ARMORED_FORM", stats=different_stats),
        pokebattler_mon("MEWTWO", 150, rarity="POKEMON_RARITY_LEGENDARY", stats=stats),
        pokebattler_mon("MEWTWO_SHADOW_FORM", 150, species="MEWTWO", family="MEWTWO",
                        rarity="POKEMON_RARITY_LEGENDARY", stats=stats),
        pokebattler_mon("MEWTWO_ARMORED_FORM", 150, species="MEWTWO", family="MEWTWO",
                        rarity="POKEMON_RARITY_LEGENDARY", form="MEWTWO_ARMORED_FORM", stats=different_stats),
        pokebattler_mon("CHARIZARD", 6, family="FAMILY_CHARMANDER", stats=stats),
        pokebattler_mon("CHARIZARD_SHADOW_FORM", 6, species="CHARIZARD", family="FAMILY_CHARMANDER", stats=stats),
        pokebattler_mon("CHARIZARD_MEGA_X", 6, species="CHARIZARD", family="FAMILY_CHARMANDER", stats=stats),
        pokebattler_mon("VENUSAUR_GIGANTAMAX", 3, species="VENUSAUR", family="FAMILY_BULBASAUR", stats=stats),
        pokebattler_mon("VENUSAUR", 3, family="FAMILY_BULBASAUR", stats=stats),
        {"pokemonId": "MISSING_DEX", "pokedex": {}},
        {"pokedex": {"pokemonNum": 1, "pokemonId": "BULBASAUR"}},
    ]
    entries = build_entries(
        pokemon_list,
        DEFAULT_NAMES,
        max_battles={"CHARIZARD", "VENUSAUR"},
    )
    by_id = entries_by_id(entries)

    assert "RATTATA_SHADOW_FORM" not in by_id
    assert "MEWTWO_SHADOW_FORM" not in by_id
    assert "CHARIZARD_SHADOW_FORM" not in by_id
    assert "MISSING_DEX" not in by_id
    assert "BULBASAUR" not in by_id

    assert "shadow" in by_id["RATTATA"]["tags"]
    assert "cosmetic" in by_id["RATTATA_SANTA_HAT_FORM"]["tags"]
    assert "shadow" in by_id["RATTATA_SANTA_HAT_FORM"]["tags"]
    assert "cosmetic" not in by_id["RATTATA_ARMORED_FORM"]["tags"]

    assert "shadow" in by_id["MEWTWO"]["tags"]
    assert "shadow" not in by_id["MEWTWO_ARMORED_FORM"]["tags"]

    assert "shadow" in by_id["CHARIZARD"]["tags"]
    assert "dynamax" in by_id["CHARIZARD"]["tags"]
    assert "shadow" not in by_id["CHARIZARD_MEGA_X"]["tags"]
    assert "dynamax" not in by_id["CHARIZARD_MEGA_X"]["tags"]
    assert "mega" in by_id["CHARIZARD_MEGA_X"]["tags"]

    assert "dynamax" in by_id["VENUSAUR"]["tags"]
    assert "dynamax" not in by_id["VENUSAUR_GIGANTAMAX"]["tags"]
    assert "gigantamax" in by_id["VENUSAUR_GIGANTAMAX"]["tags"]


def test_build_entries_tags_real_costumes_as_cosmetic():
    pikachu_stats = {"baseAttack": 112, "baseDefense": 96, "baseStamina": 111}
    gengar_stats = {"baseAttack": 261, "baseDefense": 149, "baseStamina": 155}
    squirtle_stats = {"baseAttack": 94, "baseDefense": 121, "baseStamina": 127}
    falinks_stats = {"baseAttack": 193, "baseDefense": 170, "baseStamina": 163}
    pokemon_list = [
        pokebattler_mon("PIKACHU", 25, family="FAMILY_PIKACHU", type_="ELECTRIC", stats=pikachu_stats),
        pokebattler_mon("PIKACHU_SHADOW_FORM", 25, species="PIKACHU", family="FAMILY_PIKACHU",
                        type_="ELECTRIC", stats=pikachu_stats),
        pokebattler_mon("PIKACHU_POP_STAR_FORM", 25, species="PIKACHU", family="FAMILY_PIKACHU",
                        form="PIKACHU_POP_STAR", type_="ELECTRIC", stats=pikachu_stats),
        pokebattler_mon("PIKACHU_DOCTOR_FORM", 25, species="PIKACHU", family="FAMILY_PIKACHU",
                        form="PIKACHU_DOCTOR", type_="ELECTRIC", stats=pikachu_stats),
        pokebattler_mon("PIKACHU_ADVENTURE_HAT_2020_FORM", 25, species="PIKACHU", family="FAMILY_PIKACHU",
                        form="PIKACHU_ADVENTURE_HAT_2020", type_="ELECTRIC", stats=pikachu_stats),
        pokebattler_mon("GENGAR", 94, family="FAMILY_GASTLY", type_="GHOST", type2="POISON", stats=gengar_stats),
        pokebattler_mon("GENGAR_COSTUME_2020_FORM", 94, species="GENGAR", family="FAMILY_GASTLY",
                        form="GENGAR_COSTUME_2020", type_="GHOST", type2="POISON", stats=gengar_stats),
        pokebattler_mon("SQUIRTLE", 7, family="FAMILY_SQUIRTLE", type_="WATER", stats=squirtle_stats),
        pokebattler_mon("SQUIRTLE_FALL_2019_FORM", 7, species="SQUIRTLE", family="FAMILY_SQUIRTLE",
                        form="SQUIRTLE_FALL_2019", type_="WATER", stats=squirtle_stats),
        pokebattler_mon("FALINKS", 870, family="FAMILY_FALINKS", type_="FIGHTING", stats=falinks_stats),
        pokebattler_mon("FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM", 870, species="FALINKS",
                        family="FAMILY_FALINKS", form="FALINKS_GOFEST_2025_TRAIN_CONDUCTOR",
                        type_="FIGHTING", stats=falinks_stats),
    ]
    entries = build_entries(pokemon_list, DEFAULT_NAMES)
    by_id = entries_by_id(entries)

    assert "PIKACHU_SHADOW_FORM" not in by_id
    assert "cosmetic" not in by_id["PIKACHU"]["tags"]
    assert "shadow" in by_id["PIKACHU"]["tags"]
    assert "cosmetic" in by_id["PIKACHU_POP_STAR_FORM"]["tags"]
    assert "shadow" in by_id["PIKACHU_POP_STAR_FORM"]["tags"]
    assert by_id["PIKACHU_POP_STAR_FORM"]["display_name"] == "Pikachu-Pop-Star"
    assert by_id["PIKACHU_POP_STAR_FORM"]["alias"] == "Pop Star Pikachu"
    assert "cosmetic" in by_id["PIKACHU_DOCTOR_FORM"]["tags"]
    assert "cosmetic" in by_id["PIKACHU_ADVENTURE_HAT_2020_FORM"]["tags"]
    assert "cosmetic" in by_id["GENGAR_COSTUME_2020_FORM"]["tags"]
    assert "shadow" not in by_id["GENGAR_COSTUME_2020_FORM"]["tags"]
    assert "cosmetic" in by_id["SQUIRTLE_FALL_2019_FORM"]["tags"]
    assert "cosmetic" in by_id["FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM"]["tags"]
    assert by_id["FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM"]["alias"] == (
        "Gofest 2025 Train Conductor Falinks"
    )


def test_normalize_shadow_name_strips_shadow_and_keeps_hyphens_otherwise():
    assert normalize_shadow_pokemon_name_for_lookup("shadow mewtwo") == "mewtwo"
    assert normalize_shadow_pokemon_name_for_lookup("SHADOW-MEWTWO") == "mewtwo"
    assert normalize_shadow_pokemon_name_for_lookup("mr-mime") == "mr-mime"
    assert normalize_shadow_pokemon_name_for_lookup("  Mewtwo  ") == "mewtwo"
    assert normalize_shadow_pokemon_name_for_lookup("") == ""
    assert normalize_shadow_pokemon_name_for_lookup(None) == ""


def test_find_pokemon_matches_name_id_and_alias(pokemon_index):
    assert find_pokemon("Mewtwo")["pokemon_id"] == "MEWTWO"
    assert find_pokemon("mr-mime")["display_name"] == "Mr. Mime"
    assert find_pokemon("MR MIME")["pokemon_id"] == "MR_MIME"
    assert find_pokemon("alolan ninetales")["pokemon_id"] == "NINETALES_ALOLA_FORM"
    assert find_pokemon("gmax venusaur")["display_name"] == "Gigantamax-Venusaur"
    assert find_pokemon("charizard-x") is None
    assert find_pokemon("charizard-x", mega=True)["pokemon_id"] == "CHARIZARD_MEGA_X"
    assert find_pokemon("missingno") is None


def test_find_pokemon_matches_costume_name_id_and_alias(pokemon_index):
    assert find_pokemon("Pikachu")["pokemon_id"] == "PIKACHU"
    assert find_pokemon("pikachu-pop-star")["pokemon_id"] == "PIKACHU_POP_STAR_FORM"
    assert find_pokemon("pop star pikachu")["display_name"] == "Pikachu-Pop-Star"
    assert find_pokemon("PIKACHU_POP_STAR")["pokemon_id"] == "PIKACHU_POP_STAR_FORM"
    assert find_pokemon("doctor pikachu")["pokemon_id"] == "PIKACHU_DOCTOR_FORM"
    assert find_pokemon("adventure hat 2020 pikachu")["pokemon_id"] == "PIKACHU_ADVENTURE_HAT_2020_FORM"
    assert find_pokemon("gengar-costume-2020")["pokemon_id"] == "GENGAR_COSTUME_2020_FORM"
    assert find_pokemon("fall 2019 squirtle")["pokemon_id"] == "SQUIRTLE_FALL_2019_FORM"
    assert find_pokemon("gofest 2025 train conductor falinks")["pokemon_id"] == (
        "FALINKS_GOFEST_2025_TRAIN_CONDUCTOR_FORM"
    )


def test_suggest_pokemon_needs_a_close_spelling(pokemon_index):
    assert suggest_pokemon("mewtw") == "Mewtwo"
    assert suggest_pokemon("zzzzzzz") is None
    assert suggest_pokemon("charizardx") is None
    assert suggest_pokemon("charizardx", mega=True) == "Charizard-X"


def test_validate_pokemon_uses_lookup_and_strips_shadow(pokemon_index):
    ok, name, suggestion, icon = validate_pokemon("shadow mewtwo", "5")
    assert ok is True
    assert name == "Mewtwo"
    assert suggestion == ""
    assert icon == "go:pm150"

    ok, name, suggestion, icon = validate_pokemon("charizard-x", "mega")
    assert ok is True
    assert name == "Charizard-X"

    ok, _, suggestion, icon = validate_pokemon("mewtw", "5")
    assert ok is False
    assert suggestion == "Mewtwo"
    assert icon == 0


def test_validate_pokemon_accepts_costume_spellings(pokemon_index):
    ok, name, suggestion, icon = validate_pokemon("pop star pikachu", "1")
    assert ok is True
    assert name == "Pikachu-Pop-Star"
    assert suggestion == ""
    assert icon == "go:pm25"

    ok, name, suggestion, _ = validate_pokemon("doctor pikachu", "1")
    assert ok is True
    assert name == "Pikachu-Doctor"

    ok, name, suggestion, _ = validate_pokemon("costume 2020 gengar", "3")
    assert ok is True
    assert name == "Gengar-Costume-2020"

    ok, name, suggestion, _ = validate_pokemon("fall 2019 squirtle", "1")
    assert ok is True
    assert name == "Squirtle-Fall-2019"


def test_validate_tier_accepts_known_aliases():
    assert validate_tier("5") == (True, "5")
    assert validate_tier("t5") == (True, "T5")
    assert validate_tier("1") == (True, "1")
    assert validate_tier("t1") == (True, "T1")
    assert validate_tier("3") == (True, "3")
    assert validate_tier("t3") == (True, "T3")
    assert validate_tier("MEGA") == (True, "Mega")
    ok, message = validate_tier("dmax")
    assert ok is False
    assert "Valid tiers are:" in message


def test_validate_weather_accepts_keys_and_suggests_typos():
    for weather in ("Clear", "rainy", "partlycloudy"):
        ok, response, suggestion = validate_weather_argument(weather)
        assert (ok, suggestion) == (True, "")
        assert response

    ok, message, suggestion = validate_weather_argument("sunn")
    assert ok is False
    assert suggestion == "sunny"
    assert "Did you mean" in message

    ok, _, suggestion = validate_weather_argument("xyzxyzxyz")
    assert ok is False
    assert suggestion == "xyzxyzxyz"


def dummy_interaction():
    return SimpleNamespace(guild=SimpleNamespace(name="Test Guild"))


def test_validate_and_format_message_builds_a_raid_embed(pokemon_index):
    ok, embed, suggestion = validate_and_format_message(
        dummy_interaction(), "5", "Mewtwo", "Clear", "5"
    )
    assert ok is True
    assert suggestion == ""
    assert embed.title == "Mewtwo"
    assert embed.thumbnail.url == image_url("go:pm150")
    assert embed.fields[0].name == "Weather"
    assert embed.fields[1].name == "Slots"
    assert embed.fields[1].value == "5"


def test_validate_and_format_message_mega_prefixes_title(pokemon_index):
    ok, embed, suggestion = validate_and_format_message(
        dummy_interaction(), "mega", "charizard-x", "windy", "8"
    )
    assert ok is True
    assert suggestion == ""
    assert embed.title == "Mega Charizard-X"
    assert embed.fields[1].value == "8"


def test_validate_and_format_message_invalid_pokemon_suggests(pokemon_index):
    ok, message, suggestion = validate_and_format_message(
        dummy_interaction(), "5", "mewtw", "Clear", "5"
    )
    assert ok is False
    assert "Test Guild" in message
    assert "Mewtwo" in suggestion


def test_species_rows_prefers_the_base_form():
    rows = species_rows([
        {"species_id": "PIKACHU", "pokemon_id": "PIKACHU_POP_STAR_FORM", "dex_num": 25, "rarity": None},
        {"species_id": "PIKACHU", "pokemon_id": "PIKACHU", "dex_num": 25, "rarity": None},
        {"species_id": "GENGAR", "pokemon_id": "GENGAR_COSTUME_2020_FORM", "dex_num": 94, "rarity": None},
    ])
    assert ("PIKACHU", 25, None) in rows
    assert sum(1 for row in rows if row[0] == "PIKACHU") == 1
    assert ("GENGAR", 94, None) in rows


def test_format_pokemon_name_and_filter_current_raids_shadow_overwrite():
    assert format_pokemon_name("MEWTWO") == "Mewtwo"
    assert format_pokemon_name("MEWTWO_SHADOW_FORM") == "Mewtwo"
    assert format_pokemon_name("NINETALES_ALOLA_FORM") == "Alolan Ninetales"
    assert format_pokemon_name("BLASTOISE_MEGA") == "Mega Blastoise"

    raids = filter_current_raids({
        "tiers": [
            {"tier": "RAID_LEVEL_5", "raids": [{"pokemon": "MEWTWO"}]},
            {"tier": "RAID_LEVEL_5_SHADOW", "raids": [{"pokemon": "MEWTWO_SHADOW_FORM"}]},
            {"tier": "RAID_LEVEL_1", "raids": [{"pokemon": "CLEFAIRY"}]},
            {"tier": "RAID_LEVEL_5_MAX", "raids": [{"pokemon": "DIALGA"}]},
        ]
    })
    assert raids["Mewtwo"]["tier"] == "RAID_LEVEL_5_SHADOW"
    assert raids["Clefairy"]["tier"] == "RAID_LEVEL_1"
    assert "Dialga" not in raids


def test_validate_invites_allows_one_through_ten():
    assert validate_invites_argument("5") == (True, "5")
    assert validate_invites_argument(10)[0] is True
    assert validate_invites_argument("0")[0] is False
    assert validate_invites_argument("11")[0] is False
    assert validate_invites_argument("lots")[0] is False


def test_current_raid_bosses_adds_shadow_spelling():
    dex = make_dex({
        "Mewtwo": {"tier": "RAID_LEVEL_5_SHADOW", "pokemon": "MEWTWO_SHADOW_FORM"},
        "Regirock": {"tier": "RAID_LEVEL_5", "pokemon": "REGIROCK"},
        "": {"tier": "RAID_LEVEL_1", "pokemon": "SKIP"},
    })
    assert dex.current_raid_bosses() == ["Mewtwo", "Regirock", "Shadow Mewtwo"]


def test_is_current_raid_boss_accepts_shadow_wording():
    dex = make_dex({
        "Mewtwo": {"tier": "RAID_LEVEL_5_SHADOW", "pokemon": "MEWTWO_SHADOW_FORM"},
    })
    assert dex.is_current_raid_boss("Mewtwo") is True
    assert dex.is_current_raid_boss("shadow mewtwo") is True
    assert dex.is_current_raid_boss("SHADOW MEWTWO") is True
    assert dex.is_current_raid_boss("Dialga") is False
    assert dex.is_current_raid_boss("") is False


def test_hyphenated_rotation_name_does_not_match_after_space_fold():
    dex = make_dex({
        "Landorus-Incarnate": {"tier": "RAID_LEVEL_5", "pokemon": "LANDORUS_INCARNATE_FORM"},
    })
    assert dex.is_current_raid_boss("Landorus-Incarnate") is False
    assert dex.is_current_raid_boss("Landorus Incarnate") is False
