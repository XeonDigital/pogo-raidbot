import re

import requests

GO_SOURCES = {
    "go": ("pokemon-go-api/assets", "main", "Pokemon"),
    "miners": ("PokeMiners/pogo_assets", "master", "Images/Pokemon/Addressable Assets"),
}
CDN = "https://cdn.jsdelivr.net/gh"
HOME_URL = f"{CDN}/PokeAPI/sprites@master/sprites/pokemon/other/home/{{shiny}}{{dex}}.png"
LEGACY_URL = f"{CDN}/PokeMiners/pogo_assets@master/Images/Pokemon%20-%20256x256/pokemon_icon_{{key}}.png"
_SHINY = ".s"


def fetch_asset_index(timeout=30):
    index = {}
    for source, (repo, branch, folder) in GO_SOURCES.items():
        response = requests.get(f"https://api.github.com/repos/{repo}/git/trees/{branch}:{folder}", timeout=timeout)
        response.raise_for_status()
        listing = response.json()
        index[source] = {entry["path"] for entry in listing.get("tree") or [] if entry.get("type") == "blob"}
    return index


def _stems(pokemon_id, species_id, dex_num, form):
    stems = [f"pm{dex_num}.fGIGANTAMAX"] if pokemon_id.endswith("_GIGANTAMAX") else []
    if pokemon_id != species_id:
        full = (form or pokemon_id).removesuffix("_FORM")
        short = full.removeprefix(species_id).strip("_")
        stems += [f"pm{dex_num}.f{short}", f"pm{dex_num}.f{full}"]
    return stems + [f"pm{dex_num}", f"pm{dex_num}.fNORMAL", f"pm{dex_num}.f{species_id}_NORMAL"]


def _find(index, stem, suffix):
    for source, files in index.items():
        if f"{stem}{suffix}.icon.png" in files:
            return f"{source}:{stem}{suffix}"
    return None


def _any_form(index, dex_num, suffix):
    pattern = re.compile(rf"pm{dex_num}\.f[A-Z0-9_]+{re.escape(suffix)}\.icon\.png")
    for source, files in index.items():
        matches = sorted(name for name in files if pattern.fullmatch(name))
        if matches:
            return f"{source}:{matches[0].removesuffix('.icon.png')}"
    return None


def resolve_sprite_keys(index, pokemon_id, species_id, dex_num, form):
    keys = []
    for suffix in ("", _SHINY):
        key = next((k for stem in _stems(pokemon_id, species_id, dex_num, form) if (k := _find(index, stem, suffix))), None)
        keys.append(key or _any_form(index, dex_num, suffix) or f"home:{dex_num}{suffix}")
    return tuple(keys)


def image_url(key):
    source, _, name = str(key).partition(":")
    if source in GO_SOURCES:
        repo, branch, folder = GO_SOURCES[source]
        return f"{CDN}/{repo}@{branch}/{folder.replace(' ', '%20')}/{name}.icon.png"
    if source == "home":
        dex, shiny = name.removesuffix(_SHINY), name.endswith(_SHINY)
        return HOME_URL.format(dex=dex, shiny="shiny/" if shiny else "")
    return LEGACY_URL.format(key=key)
