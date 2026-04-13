"""TIER"""
TIERS = ("t1","t3","t5","1","3","5","mega")

"""Creates the error message string for the author providing an invalid tier in the post_raid command"""
def format_invalid_tier_message(tier):
  AUTHOR_DM = "You gave an invalid **Tier** of [`" + tier + "`]. Valid tiers are: "
  for index, item in enumerate(TIERS):
    AUTHOR_DM += item.title()
    if index < len(TIERS) - 1:
      AUTHOR_DM += ", "
  AUTHOR_DM += "\n"
  return AUTHOR_DM

"""----------------------------------------------------------------"""
"""GYM COLOR"""
GYM_COLORS =\
{
  "red":"valor",
  "blue":"mystic",
  "yellow":"instinct",
  "grey":"unclaimed"
}

GYM_COLOR_HEX =\
{
  "Valor":0xff0000,
  "Mystic":0x3498db,
  "Instinct":0xefd319,
  "Unclaimed":0x808080
}

GYM_COLOR_EMOJI_ID =\
{
  "Valor":'751963981350174771',
  "Mystic":'751963922084397096',
  "Instinct":'751964018272370778',
  "Unclaimed":'751963953575362620'
}

def validate_gym_argument(gym_color):
  gym_color = gym_color.lower()
  is_valid = False
  string_to_return = ""
  """Search for valid gym color by color (dictionary keys)"""
  if gym_color in GYM_COLORS.keys():
    string_to_return = GYM_COLORS.get(gym_color)
    is_valid = True
  else:
    """Search for valid gym color by team name (dictionary values)"""
    for key, value in GYM_COLORS.items():
      if gym_color == value:
        string_to_return = value
        is_valid = True
  string_to_return = string_to_return if is_valid else format_invalid_gym_message(gym_color)
  return (is_valid, string_to_return)

"""Iterates over the GYM_COLORS dictionary and appends all keys with values to the string."""
def format_invalid_gym_message(gym_color):
  AUTHOR_DM = "You gave an invalid **Gym Color** of [`" + gym_color + "`]. Valid gym colors are: "
  for index, (color, team) in enumerate(GYM_COLORS.items()):
    AUTHOR_DM += color.title() + " or " + team.title()
    if index < len(GYM_COLORS) - 1:
      AUTHOR_DM += ", "
  AUTHOR_DM += "\n"
  return AUTHOR_DM
"""----------------------------------------------------------------"""
"""WEATHER"""
WEATHER_TO_EMOJI =\
{
  "sunny":"☀️",
  "clear":"☀️",
  "windy":"🪁",
  "partlycloudy":"⛅",
  "cloudy":"☁️",
  "rainy":"🌧️",
  "snow":"❄️",
  "fog":"🌫️"
}

WEATHER_TO_OUTPUT =\
{
  "sunny":"Sunny/Clear",
  "clear":"Sunny/Clear",
  "windy":"Windy",
  "partlycloudy":"Partly Cloudy",
  "cloudy":"Cloudy",
  "rainy":"Rainy",
  "snow":"Snow",
  "fog":"Fog"
}

def validate_weather_argument(weather):
  weather = weather.lower()
  emoji = ""
  is_valid = False
  string_to_return = ""
  """Search for valid weather type (dictionary keys)"""
  if weather in WEATHER_TO_OUTPUT.keys():
    string_to_return = WEATHER_TO_OUTPUT.get(weather)
    emoji = WEATHER_TO_EMOJI.get(weather)
    is_valid = True
  else:
    string_to_return = format_invalid_weather_message(weather)
  return (is_valid, string_to_return, emoji)
  
    
def format_invalid_weather_message(weather):
  AUTHOR_DM = "You gave an invalid **Weather** of [`" + weather + "`]. Valid weather conditions are: "
  for index, (key, value) in enumerate(WEATHER_TO_OUTPUT.items()):
    AUTHOR_DM += key.title()
    if index < len(WEATHER_TO_OUTPUT) - 1:
      AUTHOR_DM += ", "
  AUTHOR_DM += "\n"
  return AUTHOR_DM
