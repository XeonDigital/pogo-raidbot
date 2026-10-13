from unittest.mock import patch

from handlers.pokebattler.pokemon_images import image_url
from handlers.pokebattler.pokebattler_dex import (
    DexPages,
    PAGE_SIZE,
    SHADOW_ATTACK_MULTIPLIER,
    SHADOW_DEFENSE_MULTIPLIER,
    form_details,
    resolve_name,
    send_dex,
    sprite_url,
)


def followup_embed(interaction):
    return interaction.followup.send.await_args.kwargs["embed"]


def followup_view(interaction):
    return interaction.followup.send.await_args.kwargs["view"]


def call_dex(run, bot, interaction, name=None, only=None, hide=None, type_=None, rarity=None, shiny=False):
    run(send_dex(bot, interaction, name, only, hide, type_, rarity, shiny))


def known_pokemon(pokemon_id="MEWTWO"):
    return patch(
        "handlers.pokebattler.pokebattler_dex.find_pokemon",
        return_value={"pokemon_id": pokemon_id},
    )


def unknown_pokemon(suggestion=None):
    return (
        patch("handlers.pokebattler.pokebattler_dex.find_pokemon", return_value=None),
        patch("handlers.pokebattler.pokebattler_dex.suggest_pokemon", return_value=suggestion),
    )


def form_row(display_name="Mewtwo", dex_num=150, tags=None, icon_key="go:pm150",
             shiny_icon_key="go:pm150.s", base_attack=300, base_defense=182, base_stamina=214):
    return {
        "display_name": display_name,
        "dex_num": dex_num,
        "tags": [] if tags is None else tags,
        "icon_key": icon_key,
        "shiny_icon_key": shiny_icon_key,
        "base_attack": base_attack,
        "base_defense": base_defense,
        "base_stamina": base_stamina,
    }


def fetch_args(bot):
    return bot.database.fetch.await_args.args


class TestDexGuards:
    def test_only_and_hide_cannot_be_the_same(self, run, bot, make_interaction, followup_text):
        interaction = make_interaction()
        call_dex(run, bot, interaction, only="mega", hide="mega")

        assert "Can't both only show and hide **mega**" in followup_text(interaction)
        bot.database.fetch.assert_not_called()

    def test_requires_a_name_or_a_filter(self, run, bot, make_interaction, followup_text):
        interaction = make_interaction()
        call_dex(run, bot, interaction)

        assert "Give a pokemon name or dex number" in followup_text(interaction)
        bot.database.fetch.assert_not_called()

    def test_unknown_name_without_suggestion(self, run, bot, make_interaction, followup_text):
        interaction = make_interaction()
        find, suggest = unknown_pokemon()
        with find, suggest:
            call_dex(run, bot, interaction, name="missingno")

        message = followup_text(interaction)
        assert "Could not find a pokemon called **missingno**" in message
        assert "Did you mean" not in message
        bot.database.fetch.assert_not_called()

    def test_unknown_name_with_suggestion(self, run, bot, make_interaction, followup_text):
        interaction = make_interaction()
        find, suggest = unknown_pokemon(suggestion="Mewtwo")
        with find, suggest:
            call_dex(run, bot, interaction, name="mewtw")

        message = followup_text(interaction)
        assert "Could not find a pokemon called **mewtw**" in message
        assert "Did you mean **Mewtwo**" in message
        bot.database.fetch.assert_not_called()


class TestResolveName:
    def test_dex_numbers_with_or_without_hash(self):
        assert resolve_name("150") == (None, 150, False, None)
        assert resolve_name("#150") == (None, 150, False, None)

    def test_known_name_returns_pokemon_id(self):
        with known_pokemon("MEWTWO"):
            assert resolve_name("Mewtwo") == ("MEWTWO", None, False, None)

    def test_whitespace_is_stripped(self):
        with known_pokemon("MEWTWO") as find:
            assert resolve_name("  Mewtwo  ") == ("MEWTWO", None, False, None)
            assert find.call_args.args[0] == "mewtwo"

    def test_shadow_in_the_name_sets_wants_shadow(self):
        with known_pokemon("MEWTWO"):
            pokemon_id, dex_num, wants_shadow, suggestion = resolve_name("shadow mewtwo")
        assert (pokemon_id, dex_num, wants_shadow, suggestion) == ("MEWTWO", None, True, None)


class TestShadowFilter:
    def test_shadow_name_sets_only_shadow(self, run, bot, make_interaction):
        interaction = make_interaction()
        with known_pokemon("MEWTWO"):
            call_dex(run, bot, interaction, name="shadow mewtwo")
        assert fetch_args(bot)[3] == ["shadow"]

    def test_shadow_name_keeps_an_existing_only_filter(self, run, bot, make_interaction):
        interaction = make_interaction()
        with known_pokemon("MEWTWO"):
            call_dex(run, bot, interaction, name="shadow mewtwo", only="mega")
        assert fetch_args(bot)[3] == ["mega"]

    def test_shadow_name_does_not_override_hide_shadow(self, run, bot, make_interaction):
        interaction = make_interaction()
        with known_pokemon("MEWTWO"):
            call_dex(run, bot, interaction, name="shadow mewtwo", hide="shadow")
        assert fetch_args(bot)[3] == []
        assert fetch_args(bot)[4] == ["shadow"]


class TestDexQuery:
    def test_maps_filters_onto_search_args(self, run, bot, make_interaction):
        interaction = make_interaction()
        call_dex(run, bot, interaction, only="costume", hide="shadow", type_="FIRE", rarity="LEGENDARY")

        _, pokemon_id, dex_num, required, excluded, type_, rarity = fetch_args(bot)
        assert (pokemon_id, dex_num) == (None, None)
        assert required == ["cosmetic"]
        assert excluded == ["shadow"]
        assert type_ == "FIRE"
        assert rarity == "LEGENDARY"

    def test_filter_only_search_is_allowed(self, run, bot, make_interaction):
        interaction = make_interaction()
        call_dex(run, bot, interaction, only="mega")

        _, pokemon_id, dex_num, required, excluded, type_, rarity = fetch_args(bot)
        assert (pokemon_id, dex_num, required, excluded, type_, rarity) == (None, None, ["mega"], [], None, None)

    def test_empty_results_are_rejected(self, run, bot, make_interaction, followup_text):
        interaction = make_interaction()
        call_dex(run, bot, interaction, only="mega")

        assert "No pokemon match those filters" in followup_text(interaction)


class TestDexListing:
    def test_named_search_sends_an_embed_and_view(self, run, bot, make_interaction):
        interaction = make_interaction()
        bot.database.fetch.return_value = [form_row()]
        with known_pokemon("MEWTWO"):
            call_dex(run, bot, interaction, name="Mewtwo")

        embed = followup_embed(interaction)
        assert embed.title == "Pokédex · Mewtwo"
        assert "**`#0150` Mewtwo ◀**" in embed.description
        assert embed.image.url == image_url("go:pm150")
        assert followup_view(interaction).total == 1

    def test_filter_only_title_is_pokedex(self, run, bot, make_interaction):
        interaction = make_interaction()
        bot.database.fetch.return_value = [form_row()]
        call_dex(run, bot, interaction, only="mega")

        assert followup_embed(interaction).title == "Pokédex"

    def test_footer_lists_active_filters(self, run, bot, make_interaction):
        interaction = make_interaction()
        bot.database.fetch.return_value = [form_row()]
        call_dex(
            run, bot, interaction,
            only="mega",
            hide="costume",
            type_="FIRE",
            rarity="ULTRA_BEAST",
            shiny=True,
        )

        footer = followup_embed(interaction).footer.text
        assert "only: Mega" in footer
        assert "hide: Costume" in footer
        assert "type: Fire" in footer
        assert "rarity: Ultra Beast" in footer
        assert "shiny sprites" in footer

    def test_shiny_uses_the_shiny_icon(self, run, bot, make_interaction):
        interaction = make_interaction()
        bot.database.fetch.return_value = [form_row()]
        with known_pokemon("MEWTWO"):
            call_dex(run, bot, interaction, name="Mewtwo", shiny=True)

        assert followup_embed(interaction).image.url == image_url("go:pm150.s")


class TestFormDetails:
    def test_stats_line_when_attack_is_present(self):
        details = form_details(form_row())
        assert "ATK 300 · DEF 182 · STA 214" in details

    def test_shadow_note_scales_battle_stats(self):
        details = form_details(form_row(tags=["shadow"]))
        attack = round(300 * SHADOW_ATTACK_MULTIPLIER)
        defense = round(182 * SHADOW_DEFENSE_MULTIPLIER)
        assert f"Can be Shadow (ATK {attack} · DEF {defense} in battle)" in details

    def test_dynamax_note_without_stat_scaling(self):
        details = form_details(form_row(tags=["dynamax"]))
        assert "• Can Dynamax" in details

    def test_missing_stats_skip_the_attack_line(self):
        details = form_details(form_row(base_attack=None, tags=["shadow"]))
        assert "ATK" not in details
        assert "• Can be Shadow" in details


class TestDexPages:
    def test_eleven_rows_split_across_two_pages(self):
        rows = [form_row(display_name=f"Form {index}", dex_num=index) for index in range(11)]
        view = DexPages(rows, "Pokédex", "")
        assert len(view.pages) == 2
        assert "page 1/2" in view.embed().footer.text
        assert f"{PAGE_SIZE + 1} forms" in view.embed().footer.text

        view.selected = PAGE_SIZE - 1
        view._move(1)
        assert (view.page, view.selected) == (1, 0)
        assert "page 2/2" in view.embed().footer.text

    def test_single_row_hides_form_and_page_controls(self):
        view = DexPages([form_row()], "Pokédex", "")
        labels = [item.label for item in view.children if getattr(item, "label", None)]
        assert labels == []

    def test_sprite_url_falls_back_to_icon_when_not_shiny(self):
        row = form_row()
        assert sprite_url(row) == image_url("go:pm150")
        assert sprite_url(row, shiny=True) == image_url("go:pm150.s")
        assert sprite_url(form_row(shiny_icon_key=None), shiny=True) == image_url("go:pm150")
