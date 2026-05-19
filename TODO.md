# TODO

1. [X] On user join, change their nickname to "Thursday"
2. [X] Every Thursday at midnight, Central time, create a new channel, "#the-final-thursday" and give @everyone perms to chat and react in it
3. [X] Every Fr*day at midnight, Central time, change channel perms to read-only for @everyone and send a message, "@everyone Thursday is gone forever."
4. [X] Every Fr*day at midnight, Central time, change the latest Thursday channel name to "#thursday-xxx" where xxx is the number of thursdays there's been so far in the server.
5. [X] Every 6 months, (or check exactly how many Thursdays are in each category) create a new channel category: "THURSDAY YEAR X (x/2)"; future thursdays will go here for the next 6 months.
6. [X] Add command for Thursday Admins to set which channels people can speak in on Thursdays; set chat perms for them at midnight on Thursdays and Fr*days.
7. [X] Add commands for Thursday Admins to change the current, past, or next Thursday channel name.
8. [X] Create db.json on the first run or read from it if it exists and contains all necessary fields: stores info such as next thursday channel name override. Gitignore this file.

## Config.json notes

"first_thursday" is yyy-mm-dd (i.e. "2019-05-02")
"guild_id": is "1504542282915905636" for my testing server but "571557702086557740" for production

guild_id will need to be changed or deleted before being put into production.
