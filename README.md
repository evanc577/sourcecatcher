# [sourcecatcher.com](https://www.sourcecatcher.com)
A reverse image search tool for InSomnia

See the [Reddit release thread](https://www.reddit.com/r/dreamcatcher/comments/c923qp/sourcecatchercom_a_reverse_image_search_tool_for/) for more information about Sourcecatcher

---

## Setup

Sourcecatcher is published as an OCI container.

### Directory structure

```
$ tree
.
├── config
│   ├── nitter
│   │   └── sessions.jsonl
│   └── sourcecatcher
│       ├── config-discord.toml
│       └── config.yaml
└── live
    ├── discord.db
    ├── phash_index.ann
    └── twitter_scraper.db
```

See [Config files](#config-files) section for configuration file setup.
The `live` directory contains Sourcecatcher's databases, it should be persisted to a host directory (See next section).

### Quadlet setup

Create quadlet generator file. Remember to configure container network and volume mounts setup.
```
$ cat ~/.config/containers/systemd/sourcecatcher.container 
[Unit]
Description=Sourcecatcher reverse image search service
After=network.target

[Container]
ContainerName=sourcecatcher
Image=ghcr.io/evanc577/sourcecatcher:latest
AutoUpdate=registry
Network=bridge
PublishPort=9000:80
Volume=/home/sourcecatcher/config/sourcecatcher/:/sourcecatcher/config/:Z,ro
Volume=/home/sourcecatcher/config/nitter/sessions.jsonl:/nitter/sessions.jsonl:Z,ro
Volume=/home/sourcecatcher/live/:/sourcecatcher/live/:Z

[Install]
WantedBy=multi-user.target default.target
```
Start the container
```console
$ systemctl --user daemon-reload
$ systemctl --user start sourcecatcher.service
```

### Config files

#### `config.yaml`

`config.yaml` contains runtime information needed by Sourcecatcher.

```yaml
# Don't need to change for OCI container
media_dir: "/sourcecatcher/images/"
nitter_instance: "http://0.0.0.0:8080"

# Image hashing options
cpus: 4
recalculate_kmeans: False

# Set to true to enable scraping discord server channels for Twitter links
scrape_discord: true

# These users will show up first in search results
priority_users:
  - "hf_dreamcatcher"
  - "jp_dreamcatcher"
  - "7_DREAMERS"
  - "2Moori"

# Set of users to scrape via Nitter
users:
  - "hf_dreamcatcher"
  - "7_DREAMERS"
  - "2Moori"
```

#### `config-discord.toml`

```
database_file = "working/discord.db"
discord_token = "your-discord-api-token"

# List of Discord channel IDs to scape
watched_channels = [
    "253293425460248580",
    "253293450030481418",
]
```

#### `sessions.jsonl`

Twitter user accounts used for running a local nitter instance.
See upstream [Nitter](https://github.com/zedeus/nitter) documentation for how to generate this file.
