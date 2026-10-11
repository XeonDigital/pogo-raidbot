import pytest

from classes.pokedex import Pokedex
from handlers.pokebattler import pokemon_lookup as lookup
from handlers.pokebattler.pokemon_lookup import (
    DEFAULT_NAMES,
    _build_index,
    _folded,
    classify,
    find_pokemon,
    normalize_key,
    suggest_pokemon,
)
from pogo_raid_lib import (
    normalize_shadow_pokemon_name_for_lookup,
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
    "VENUSAUR",
    "RATTATA",
}


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


def test_folded_shadow_maps_to_base_or_form_id():
    assert _folded("MEWTWO_SHADOW_FORM", {"MEWTWO", "MEWTWO_SHADOW_FORM"}) == ("shadow", "MEWTWO")
    assert _folded("RATTATA_ALOLA_SHADOW_FORM", {"RATTATA_ALOLA_FORM", "RATTATA_ALOLA_SHADOW_FORM"}) == (
        "shadow",
        "RATTATA_ALOLA_FORM",
    )
    assert _folded("MEWTWO", {"MEWTWO"}) is None


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


def test_validate_tier_accepts_known_aliases():
    assert validate_tier("5") == (True, "5")
    assert validate_tier("t5") == (True, "T5")
    assert validate_tier("MEGA") == (True, "Mega")
    ok, message = validate_tier("dmax")
    assert ok is False
    assert "Valid tiers are:" in message


def test_validate_weather_accepts_keys_and_suggests_typos():
    ok, response, suggestion = validate_weather_argument("Clear")
    assert ok is True
    assert response
    assert suggestion == ""

    ok, message, suggestion = validate_weather_argument("sunn")
    assert ok is False
    assert suggestion == "sunny"
    assert "Did you mean" in message

    ok, _, suggestion = validate_weather_argument("xyzxyzxyz")
    assert ok is False
    assert suggestion == "xyzxyzxyz"


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
