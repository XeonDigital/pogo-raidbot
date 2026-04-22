# Setting up for your own local

## Requirements
test

### Python 3
This bot runs on python3

### PostGreSQL
This bot uses postgreSQL as its database. Setting up a database with a good tool is recommended. Download PostGreSQL and I'm personally using DBeaver to view the database. Make sure to make your own local copy of `.env` based on `.env.example` and fill in the database related fields so that your application connects to your local database. 

### Discord

To do some local testing, you would want to have a discord server where you can test the bot in. Discord has its own developer portal for its bots and you will be able to generate a token to run the bot in testing mode (live mode requires its own flag) so it connects to your server. If you're new to discord bots like me, I'd recommend https://www.youtube.com/watch?v=CHbN_gB30Tw&list=PL-7Dfw57ZZVQ-GCNQS4Kyz637Fffhb0Hs to see how to set it up

### Setup

Once you have the above set up, you can start running the python scripts to get started on testing locally. 

```python
pip install -r requirements.txt
python3 init_database.py
python3 main.py
```

Your application should now start running and Resh's logs should start appearing 
```
Loaded: cogs.member_commands
Loaded: cogs.registration_commands
Loaded: cogs.admin_commands
Loaded: cogs.general_commands
Loaded: cogs.event_listeners
Loaded: cogs.raid_cog
Loaded: cogs.command_error_listener
```
Now you can start testing the commands in your local discord server. Note, you want to prefix your commands with a dash. 

Registering a raid channel: `-register_raid_channel`