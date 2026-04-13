import discord

def handle_get_pokemon_by_number(bot, dex_number=0):
    if dex_number < 0 or dex_number > 809:
        return

    pokedex = bot.dex

    for entry in pokedex:
        pokedex_data = entry.get("pokedex")
        if pokedex_data.get("pokemonNum") == dex_number:
            print(entry)
            

def handle_get_pokemon_by_name(bot, tier="None", name="None"):
    pokedex = bot.dex

    for entry in pokedex:
        entry_name = entry.get("pokemonId")
        if entry_name == name:
            return entry

async def retrieve_pokedex_data(bot, ctx, arg1="None", arg2="None"):
    print(arg1, arg2)
    result = None
    if arg1 == "Mega" and not arg2 == "None":
        result = handle_get_pokemon_by_name(arg1, arg2)
    if not result:
        result = handle_get_pokemon_by_name(None, arg1)
    
    if arg1.isnumeric():
        result = handle_get_pokemon_by_number(int(arg1))
    
    if not result:
        return
    
    return result
