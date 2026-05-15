# TODO

1. On user join, change their nickname to "Thursday" (done)
2. Every Thursday at midnight, Central time, create a new channel, "#the-final-thursday" and give @everyone perms to chat and react in it (done)
3. Every Fr*day at midnight, Central time, change channel perms to read-only for @everyone and send a message, "@everyone Thursday is gone forever." (done)
4. Every Fr*day at midnight, Central time, change the latest Thursday channel name to "#thursday-xxx" where xxx is the number of thursdays there's been so far in the server. (done)
5. Every 6 months, (or check exactly how many Thursdays are in each category) create a new channel category: "THURSDAY YEAR X (x/2)"; future thursdays will go here for the next 6 months. (done)
6. Add commands for Thursday Admins to change the current, past, or next Thursday channel name.
7. Create db.json on the first run or read from it if it exists and contains all necessary fields: stores info such as next thursday channel name override. Gitignore this file.
8. ~~Auto-delete blasphemous messages that praise fr*day or curse Thursday. (very limited vocabulary blacklist for now)~~ (scrapped for now)

## Config.json notes

"first_thursday" is yyy-mm-dd (i.e. "2019-05-02")
"guild_id": is "1504542282915905636" for testing server but "571557702086557740" for production
"thursday_category_id": is "1504561000563609720" for testing but is temporary hopefully and will not be needed once this is production ready, hopefully.

guild_id and thursday_category_id will need to be changed or deleted before being put into production.

