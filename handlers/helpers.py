"""Helper functions"""
def guild_member_dm(guild_name, message):
    return "**From:** {} raid hosting bot\n{}".format(guild_name, message)

def get_pokemon_name_from_raid(message):
    embed = message.embeds[0]
    title = embed.title
    if title.startswith("Mega ", 0, 5):
        return True, title.split(" ")[1]
    return False, title
