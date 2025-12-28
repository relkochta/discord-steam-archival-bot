# Discord Steam Archival Bot

[Shared Steam clips](https://store.steampowered.com/gamerecording) expire after only 2 days.
This Discord bot automatically downloads every Steam clip posted on a Discord server and replies with an archival link.
Steam clips are identified as videos hosted on the `cdn.steamusercontent.com` domain.

The downloaded clips can be served using any static web server (for example, nginx).

# Necessary Permissions

Scopes:
- **bot**

Bot Permissions:
- Add Reactions

# Docker Compose

Here's an example (untested!) `docker-compose.yml` to give a sense of how the bot is intended to be used:

```yml
services:
  app:
    image: [BUILT IMAGE ID]
    user: 1010:1010
    volumes:
      - "/path/to/clips:/clips"
      - "/path/to/db:/db"
    env:
      BASE_URL: "https://steam-clip-archive.example.com"
      BOT_TOKEN: "YOUR BOT TOKEN HERE"

  nginx:
    image: nginxinc/nginx-unprivileged
    user: 1010:1010
    volumes:
      - "/path/to/clips:/usr/share/nginx/html:ro"
    ports:
      - 443:443
```

# Roadmap

Things that should be added at some point:

- Delete archival replies if original message is deleted
- Enable only on specific channel(s)
