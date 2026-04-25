# Pokemon Go Raid hosting bot
This is yet another implementation of a raid hosting framework for use within the r/pokemongo discord. It can be hosted on a raspberry pi or any VPS.

## Requirements
Make sure you have installed these before proceding:
- Python 3
- PostgreSQL

## Installation

### Dependencies
First create a new python enviornment by running (<ins>Replace the path to match the current folder</ins>)

```
python -m venv /path/to/folder/
```

To activate the enviornment run the following:

**Windows**:

For powershell
```
source /path/to/folder/.venv/bin/activate.ps1
```

For cmd

```
source /path/to/folder/.venv/bin/activate.bat
```

**Linux**:

For bash
```
source /path/to/folder/.venv/bin/activate
```

After successfully activating the enviornment, install the required dependencies by running: 
```
pip install -r requirements.txt
```
### Setup 

Make sure you have created a discord application [here](https://discord.com/developers/applications)

Copy the .env.example and rename it to .env and fill in the contents required to run the bot

After that you can now run the main.py file

## Use
### Discord Server Setup
***All this is required to properly run the bot***

To set up the bot to work in your discord server, set up a designated raid channel and run the command `<prefix>register_raid_channel` with your prefix.

Then to register the request module, set up a designated request channel and run `<prefix>register_request_channel`.

The bot will automatically remove any posts that are not proper, ignoring users with moderator permissions, from the two channels above.

Then to register a lobby category, open an empty channel in a category and run `<prefix>register_raid_lobby_category`.

Finally to setup the management channel system, add a new channel to the above category and run the command `<prefix>register_lobby_manager_channel`.

### Posting a raid
The hosting user would type the following in the preferred raid channel:

`<prefix>(r, R, raid, Raid) Tier Name Weather Invites`
An example would be:
`-r mega gengar clear` (The invite slots default to five if not provided)
`-r 5 charizard rainy`

## Notes
Any part that the user gets wrong will be pointed out specifically and sent to the raid host in a DM, along with valid options pulled directly from what it uses to check again.

For the pokemon name and weather, it will attempt to perform a fuzzy search and suggest a correction. This correction along with the rest of the command that was given will be sent back to the user so they can copy and paste it back into the channel after verifying.
