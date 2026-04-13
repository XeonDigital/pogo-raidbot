import discord
from discord.ext import commands
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from data.formats import *
from data.pokemon import *
import handlers.helpers as H
#from bot_lib import wrap_bot_dm
import re


def build_image_link_serebii(num):
    num = str(num).zfill(3)
    return "https://www.serebii.net/swordshield/pokemon/{}.png".format(num)

def build_image_link_github(num):
    return "http://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Images/Pokemon%20-%20256x256/pokemon_icon_{}.png".format(str(num))


def validate_and_format_message(ctx,
                                tier,
                                pokemon_name,
                                weather,
                                invite_slots):
    # Format raid post
    raid_post_valid = True
    author_dm = H.guild_member_dm(ctx.guild.name, "")
    corrected_argument_guesses = {}
    """----------------------------------------------------------------"""
    is_valid, response = validate_tier(tier)
    if is_valid:
        embed_tier = response.title()
    else:
        raid_post_valid = False
        author_dm += response
    """----------------------------------------------------------------"""
    is_valid, response, suggestion, number = validate_pokemon(pokemon_name, tier)
    if is_valid:
        embed_pokemon   = response.title()
        embed_thumbnail = build_image_link_github(number)
    else:
        raid_post_valid = False
        corrected_argument_guesses.update({"pokemon_name" : suggestion})
        author_dm += response
    """----------------------------------------------------------------"""
    #is_valid, response, suggestion = validate_gym_argument(gym_color)
    #if is_valid:
    #  embed_gym = response.title()
    #else:
    #  raid_post_valid = False
    #  corrected_argument_guesses.update({"gym_color" : suggestion})
    #  author_dm += response
    """----------------------------------------------------------------"""
    is_valid, response, suggestion = validate_weather_argument(weather)
    if is_valid:
        embed_weather = response.title()
    else:
        raid_post_valid = False
        corrected_argument_guesses.update({"weather" : suggestion})
        author_dm += response
    """----------------------------------------------------------------"""
    is_valid, response = validate_invites_argument(invite_slots)
    if is_valid:
      embed_invites = response
    else:
      raid_post_valid = False
      author_dm += response
    """----------------------------------------------------------------"""
    #is_valid, response = validate_tts_argument(time_to_start)
    #if is_valid:
    #  embed_tts = str(response)
    #else:
    #  raid_post_valid = False
    #  author_dm += response
    """----------------------------------------------------------------"""
    # is_valid, response = validate_tte_argument(time_to_expire)
    # if is_valid:
    #     embed_tte = str(response)
    # else:
    #     raid_post_valid = False
    #     author_dm += response
    """----------------------------------------------------------------"""
    #if is_valid:
    #  is_valid, response = check_tts_tte(time_to_start, time_to_expire)
    #  if not is_valid:
    #    raid_post_valid = False
    #    author_dm += response

    if raid_post_valid:
        title = embed_pokemon
        if tier.lower() == "mega":
            title = "Mega " + embed_pokemon
        embed = discord.Embed(title=title, description="", color=0xff8c00)#get_embed_color(gym_color))
        if embed_pokemon in POKEBATTLER_LINK:
            embed.url = POKEBATTLER_LINK.get(embed_pokemon)
            embed.description = "Click the Pokemon name above for more in depth counter information."
        embed.set_thumbnail(url=embed_thumbnail)
        embed.add_field(name="Weather", value=embed_weather, inline=True)
        embed.add_field(name="Slots", value=embed_invites, inline=True)
        embed.set_footer(text="To join this raid, DM the host above.")
        if embed_pokemon in RAID_COUNTER_GUIDE:
            embed.set_image(url=RAID_COUNTER_GUIDE.get(embed_pokemon))
        """Send Message"""
        return (raid_post_valid, embed, "")
    else:
        suggested_command_format = format_command_suggestion(tier,
                                                             pokemon_name,
                                                             weather,
                                                             invite_slots,
                                                             corrected_argument_guesses)
        return (raid_post_valid, author_dm, suggested_command_format)

"""----------------------------------------------------------------"""
"""TIER"""
# Creates the error message string for the author providing an invalid tier in the post_raid command
def validate_tier(tier):
    tier = tier.lower()
    response = ""
    is_valid = True

    if tier.lower() in TIERS:
        response = tier.title()
    else:
        is_valid = False
        response = format_invalid_tier_message(tier)

    return(is_valid, response)

def format_invalid_tier_message(tier):
    response = "You gave an invalid **Tier** of " + backtick_and_bracket(tier) + ". Valid tiers are: "

    for index, item in enumerate(TIERS):
        response += item.title()
        if index < len(TIERS) - 1:
            response += ", "

    response += "\n"
    return response
"""----------------------------------------------------------------"""
"""POKEMON NAME"""
def validate_pokemon(pokemon_name, tier):
    pokemon_name = pokemon_name.lower()
    is_valid = False
    suggestion = ""
    dex_num = 0

    if "mega" in tier.lower():
        for number, name in MEGA_DEX.items():
            if pokemon_name == name.lower():
                response = name.title()
                dex_num = number
                is_valid = True
                break
    else:
        for number, name in NATIONAL_DEX.items():
            if pokemon_name == name.lower():
                response = name.title()
                dex_num = number
                is_valid = True
                break

        if not is_valid:
            for number, name in GALARIAN_DEX.items():
                if pokemon_name == name.lower():
                    response = name.title()
                    dex_num = number
                    is_valid = True
                    break

        if not is_valid:
            for number, name in ALOLAN_DEX.items():
                if pokemon_name == name.lower():
                    response = name.title()
                    dex_num = number
                    is_valid = True
                    break

        if not is_valid:
            for number, name in ALTERNATE_FORME_DEX.items():
                if pokemon_name == name.lower():
                    response = name.title()
                    dex_num = number
                    is_valid = True
                    break

    if not is_valid:
        response, suggestion = format_invalid_pokemon_message(pokemon_name, tier)

    return (is_valid, response, suggestion, dex_num)

def format_invalid_pokemon_message(pokemon_name, tier):
    response = "You gave an invalid **Pokemon Name** of " + backtick_and_bracket(pokemon_name) + "."
    best_ratio = 0
    suggestion = ""

    if "mega" in tier.lower():
        for name in MEGA_DEX.values():
            fuzz_ratio = fuzz.ratio(pokemon_name, name.lower())
            if fuzz_ratio > best_ratio:
                best_ratio = fuzz_ratio
                suggestion = name.lower()
    else:
        for name in NATIONAL_DEX.values():
            fuzz_ratio = fuzz.ratio(pokemon_name, name.lower())
            if fuzz_ratio > best_ratio:
                best_ratio = fuzz_ratio
                suggestion = name.lower()

        for name in GALARIAN_DEX.values():
            fuzz_ratio = fuzz.ratio(pokemon_name, name.lower())
            if fuzz_ratio > best_ratio:
                best_ratio = fuzz_ratio
                suggestion = name.lower()

        for name in ALOLAN_DEX.values():
            fuzz_ratio = fuzz.ratio(pokemon_name, name.lower())
            if fuzz_ratio > best_ratio:
                best_ratio = fuzz_ratio
                suggestion = name.lower()

        for name in ALTERNATE_FORME_DEX.values():
            fuzz_ratio = fuzz.ratio(pokemon_name, name.lower())
            if fuzz_ratio > best_ratio or fuzz_ratio == best_ratio:
                best_ratio = fuzz_ratio
                suggestion = name.lower()

    response += "\n"

    if best_ratio > 75:
        response += "Did you mean " + backtick_and_bracket(suggestion.title()) + "?"
    else:
        response += "Could not find a reliable close match based on given parameter " + backtick_and_bracket(pokemon_name)
        suggestion = pokemon_name

    response += "\n"
    return response, suggestion

"""----------------------------------------------------------------"""
"""GYM COLOR"""
def validate_gym_argument(gym_color):
    gym_color = gym_color.lower()
    is_valid = False
    suggestion = ""
    for key, value in GYM_COLOR_TO_CONTROL_TEAM.items():
        if gym_color == key:
            gym_control = value
            is_valid = True
            break
        elif gym_color == value:
            gym_control = value
            is_valid = True
            break

    if is_valid:
        gym_control = gym_control.title()
        response = gym_control + " <:gym" + gym_control.lower() + ":" + GYM_CONTROL_EMOJI_ID.get(gym_control) + ">"
    else:
        response, suggestion = format_invalid_gym_message(gym_color)

    return (is_valid, response, suggestion)

# Iterates over the GYM_COLOR_TO_CONTROL_TEAM dictionary and appends all keys with values to the string.
def format_invalid_gym_message(gym_color):
    response = "You gave an invalid **Gym Color** of " + backtick_and_bracket(gym_color) + ". Valid gym colors are: "
    best_ratio = 0
    suggestion = ""
    for index, (color, team) in enumerate(GYM_COLOR_TO_CONTROL_TEAM.items()):
        response += color.title() + " or " + team.title()
        if index < len(GYM_COLOR_TO_CONTROL_TEAM) - 1:
            response += ", "

        fuzz_ratio = fuzz.ratio(gym_color, color.lower())
        if fuzz_ratio > best_ratio:
            best_ratio = fuzz_ratio
            suggestion = color.lower()

        fuzz_ratio = fuzz.ratio(gym_color, team.lower())
        if fuzz_ratio > best_ratio:
            best_ratio = fuzz_ratio
            suggestion = team.lower()

    response += "\n"

    if best_ratio > 75:
        response += "Did you mean [`" + suggestion.title() + "`]?"
    else:
        response += "Could not find a reliable close match based on given parameter " + backtick_and_bracket(gym_color)
        suggestion = gym_color

    response += "\n"
    return (response, suggestion)


def get_embed_color(gym_color):
    gym_color = gym_color.lower()
    response = GYM_CONTROL_COLOR_HEX.get("Unclaimed")

    for key, value in GYM_COLOR_TO_CONTROL_TEAM.items():
        if gym_color == key:
            gym_control = value
        elif gym_color == value:
            gym_control = value

    response = GYM_CONTROL_COLOR_HEX.get(gym_control.title())
    return response
"""----------------------------------------------------------------"""
"""WEATHER"""

def validate_weather_argument(weather):
    weather = weather.lower()
    is_valid = False
    suggestion = ""
    # Search for valid weather type (dictionary keys)
    if weather in WEATHER_TO_OUTPUT.keys():
        response = f"{WEATHER_TO_EMOJI.get(weather)}"# {WEATHER_TO_OUTPUT.get(weather)}"
        is_valid = True
    else:
        response, suggestion = format_invalid_weather_message(weather)
    return (is_valid, response, suggestion)


def format_invalid_weather_message(weather):
    response = "You gave an invalid **Weather Condition** of " + backtick_and_bracket(weather) + ". Valid weather conditions are: "
    best_ratio = 0
    suggestion = ""
    for index, (key, _) in enumerate(WEATHER_TO_OUTPUT.items()):
        response += key.title()
        if index < len(WEATHER_TO_OUTPUT) - 1:
            response += ", "

        fuzz_ratio = fuzz.ratio(weather, key.lower())
        if fuzz_ratio > best_ratio:
            best_ratio = fuzz_ratio
            suggestion = key.lower()

    response += "\n"

    if best_ratio > 75:
        response += "Did you mean " + backtick_and_bracket(suggestion.title()) + "?"
    else:
        response += "Could not find a reliable close match based on given parameter " + backtick_and_bracket(weather)
        suggestion = weather

    response += "\n"

    return (response, suggestion)

"""----------------------------------------------------------------"""
"""INVITE COUNT"""
def validate_invites_argument(invite_slots):
    is_valid = False
    response = ""
    try:
        invite_slots = int(invite_slots)
        if invite_slots > 0 and invite_slots <= 10:
            is_valid = True
            response = str(invite_slots)
    except ValueError:
        response = backtick_and_bracket(invite_slots) + " is not a valid number."
        response += "\n"

    if not is_valid:
        response += format_invalid_invites_message()
        response += "\n"

    return (is_valid, response)

def format_invalid_invites_message():
    return "**Invite slots** must be a number from `1` - `10`."

"""----------------------------------------------------------------"""
"""TIME TO START"""
def validate_tts_argument(tts):
    is_valid = False
    response = ""
    try:
        tts = int(tts)
        if tts >= 0 and tts <= 45:
            is_valid = True
    except ValueError:
        response = backtick_and_bracket(tts) + " is not a valid number."
        response += "\n"


    if is_valid:
        if tts == 0:
            response = "As soon as possible."
        else:
            response = str(tts) + " minutes"
    else:
        response += format_invalid_tts_message()
        response += "\n"

    return (is_valid, response)

def format_invalid_tts_message():
    return "**Time to start** must be greater than or equal to " + backtick_and_bracket("0") + "."

"""----------------------------------------------------------------"""
"""TIME TO EXPIRE"""
def validate_tte_argument(tte):
    is_valid = False
    response = ""
    try:
        tte = int(tte)
        if tte >= 10 and tte <= 45:
            is_valid = True
            response = str(tte) + " minutes"
        if tte == 0:
            is_valid = True
            response = 10
    except ValueError:
        response = backtick_and_bracket(tte) + " is not a valid number."
        response += "\n"

    if not is_valid:
        response += format_invalid_tte_message()
        response += "\n"

    return (is_valid, response)

def format_invalid_tte_message():
    return "**Time to expire** must be between " + backtick_and_bracket("10") + " minutes and " + backtick_and_bracket("45") + " minutes if a custom value is specified."


"""----------------------------------------------------------------"""
"""TTS VS TTE"""
def check_tts_tte(tts, tte):
    tts = int(tts)
    tte = int(tte)
    is_valid = False
    response = ""
    if tts <= (tte - 10):
        is_valid = True
    else:
        response = format_invalid_tts_tte_message()
        response += "\n"

    return (is_valid, response)

def format_invalid_tts_tte_message():
    return "**Time to start** cannot be less than ten minutes from the time the raid expires."

"""----------------------------------------------------------------"""
"""MISC"""
# Add a bracket and backtick around a string
def backtick_and_bracket(string):
    return "[`" + string + "`]"

# Append a space to the end of the string
def sp(string):
    return str(string) + " "

def format_command_suggestion(tier,
                                                            pokemon_name,
                                                            #gym_color,
                                                            weather,
                                                            #invite_slots,
                                                            #time_to_start,
                                                            time_to_expire,
                                                            corrected_argument_guesses):

    if "pokemon_name" in corrected_argument_guesses:
        pokemon_name = corrected_argument_guesses.get("pokemon_name")
    #if "gym_color" in corrected_argument_guesses:
    #  gym_color = corrected_argument_guesses.get("gym_color")
    if "weather" in corrected_argument_guesses:
        weather = corrected_argument_guesses.get("weather")

    response = sp(tier) +\
                         sp(pokemon_name) +\
                         sp(weather) +\
                         sp(time_to_expire)
    return response

"""----------------------------------------------------------------"""
"""USER MANAGEMENT"""
def validate_level(level):
    is_valid = True
    try:
        level = int(level)
        response = str(level)
        if level <= 0 or level > 40:
            is_valid = False
            response = backtick_and_bracket(response)
            response += " is not a valid level. Level must be from " + backtick_and_bracket("1") + " to " + backtick_and_bracket("40")
        else:
            response = str(level)
    except ValueError:
        is_valid = False
        response = backtick_and_bracket(str(level)) + " is not a valid number"

    return (is_valid, response)

def validate_friend_code_format(friend_code, friend_code_middle, friend_code_end):
    is_valid = True
    friend_code = friend_code + friend_code_middle + friend_code_end
    friend_code_regex = re.compile('^\\d{12}$')

    fc = friend_code_regex.match(friend_code)
    if fc and fc.end() == 12:
        response = fc.group()
    else:
        response = "No friend code detected in given input: " + backtick_and_bracket(friend_code)

    return (is_valid, response)
