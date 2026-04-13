# Pokemon Go Raid hosting bot
This is yet another implementation of a raid hosting framework for use within the r/pokemongo discord. It can be hosted on a raspberry pi or any VPS.

## Requirements

### Python 3
This bot runs on python3

### discord.py module

Installation instructions and documentation for the entire discord.py library can be found at https://pypi.org/project/discord.py/

### Fuzzywuzzy module

```pip install fuzzywuzzy```

This is used to attempt to provide corrections for typos and suggest it back to the hosting user in a DM.

## Use
### Bot Hosting
To set up the bot to work in your discord server, set up a designated raid channel and run the command `register_raid_channel`.

To register the request module, set up a designated request channel and run `register_request_channel`.

The bot will automatically remove any posts that are not proper, ignoring users with moderator permissions, from the two channels above.

To register a lobby category, open an empty channel in a category and run `register_raid_lobby_category`.

If you want to use the management channel system, add a new channel to the above category and run the command `register_lobby_management_channel`.

### Posting a raid
The hosting user would type the following in the preferred raid channel:

`<prefix>(r, R, raid, Raid) Tier Name Weather Invites`
An example would be:
`-r mega gengar clear` (The invite slots default to five if not provided)
`-r 5 charizard rainy`

## Notes
Any part that the user gets wrong will be pointed out specifically and sent to the raid host in a DM, along with valid options pulled directly from what it uses to check again.

For the pokemon name and weather, it will attempt to perform a fuzzy search and suggest a correction. This correction along with the rest of the command that was given will be sent back to the user so they can copy and paste it back into the channel after verifying.
