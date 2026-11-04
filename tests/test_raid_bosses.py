from cogs.general_commands import build_raid_bosses_embed


def field_names(embed):
    return [field.name for field in embed.fields]


def field_value(embed, name):
    for field in embed.fields:
        if field.name == name:
            return field.value
    return None


def test_empty_cache_asks_to_refresh():
    embed = build_raid_bosses_embed({})
    assert "No raid bosses cached" in embed.description
    assert len(embed.fields) == 0


def test_missing_tiers_are_omitted():
    embed = build_raid_bosses_embed({
        "Mewtwo": {"tier": "RAID_LEVEL_5", "pokemon": "MEWTWO"},
        "Gengar": {"tier": "RAID_LEVEL_MEGA", "pokemon": "GENGAR"},
    })
    names = field_names(embed)
    assert "Mega" in names
    assert "Tier 5" in names
    assert "Tier 1" not in names
    assert "Shadow Tier 5" not in names
    assert not embed.description


def test_shadow_and_regular_bosses_go_to_separate_fields():
    embed = build_raid_bosses_embed({
        "Mewtwo": {"tier": "RAID_LEVEL_5", "pokemon": "MEWTWO"},
        "Shadow Mewtwo": {"tier": "RAID_LEVEL_5_SHADOW", "pokemon": "MEWTWO_SHADOW_FORM"},
    })
    assert "Mewtwo" in field_value(embed, "Tier 5")
    assert "Shadow Mewtwo" in field_value(embed, "Shadow Tier 5")
    assert "Shadow Mewtwo" not in field_value(embed, "Tier 5")


def test_bosses_in_a_tier_are_sorted():
    embed = build_raid_bosses_embed({
        "Zapdos": {"tier": "RAID_LEVEL_5", "pokemon": "ZAPDOS"},
        "Articuno": {"tier": "RAID_LEVEL_5", "pokemon": "ARTICUNO"},
        "Moltres": {"tier": "RAID_LEVEL_5", "pokemon": "MOLTRES"},
    })
    assert field_value(embed, "Tier 5") == "Articuno\nMoltres\nZapdos"


def test_grouped_cache_lists_keep_shadow_and_regular():
    embed = build_raid_bosses_embed({
        "Mewtwo": [
            {"tier": "RAID_LEVEL_5", "pokemon": "MEWTWO"},
            {"tier": "RAID_LEVEL_5_SHADOW", "pokemon": "MEWTWO_SHADOW_FORM"},
        ],
    })
    assert "Mewtwo" in field_value(embed, "Tier 5")
    assert "Shadow Mewtwo" in field_value(embed, "Shadow Tier 5")


def test_elite_and_mega_legendary_are_not_lumped_into_mega():
    embed = build_raid_bosses_embed({
        "Gengar": {"tier": "RAID_LEVEL_MEGA", "pokemon": "GENGAR_MEGA"},
        "Rayquaza": {"tier": "RAID_LEVEL_MEGA_5", "pokemon": "RAYQUAZA_MEGA"},
        "Enamorus": {"tier": "RAID_LEVEL_ELITE", "pokemon": "ENAMORUS"},
    })
    assert field_value(embed, "Mega") == "Gengar"
    assert field_value(embed, "Mega Legendary") == "Rayquaza"
    assert field_value(embed, "Elite") == "Enamorus"
    assert "Enamorus" not in (field_value(embed, "Mega") or "")
    assert "Rayquaza" not in (field_value(embed, "Mega") or "")


def test_blank_names_are_skipped():
    embed = build_raid_bosses_embed({
        "": {"tier": "RAID_LEVEL_1", "pokemon": "SKIP"},
        "Clefairy": {"tier": "RAID_LEVEL_1", "pokemon": "CLEFAIRY"},
    })
    assert field_value(embed, "Tier 1") == "Clefairy"
    assert "No raid bosses cached" not in (embed.description or "")
