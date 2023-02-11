# [sourcecatcher.com](https://www.sourcecatcher.com)
A reverse image search tool for InSomnia

See the [Reddit release thread](https://www.reddit.com/r/dreamcatcher/comments/c923qp/sourcecatchercom_a_reverse_image_search_tool_for/) for more information about Sourcecatcher

---

## Setup

Sourcecatcher has been tested on Arch Linux and Ubuntu 19.04.
It should also work on many other Linux distros.

### Install requirements

#### Required system packages

* ffmpeg
* [tweet-scraper](https://github.com/evanc577/tweet-scraper)
    * chromium

#### Python modules

Sourcecatcher has been tested on python 3.7, but should work on other recent versions of python 3 also

```bash
python -m venv sourcecatcher_venv           # create python virtual environment
source ./sourcecatcher_venv/bin/activate
pip install -r requirements.txt
````

### Create `config.yaml`

`config.yaml` contains runtime information needed by Sourcecatcher.
You will need to apply for the Twitter api and create an app.

```yaml
media_dir: "path/to/directory/to/store/images"

users:
  - "twitter user to scrape 1"
  - "user 2"
  - "user 3"
```

### Create and update the database

The bash scripts are used for creating and updating Sourceactcher's internal database

```bash
./initial.sh      # create/recreate the database. scrapes all users, may take a few hours
./update.sh       # fetch the latest tweets and update the database, also backups the current databse
./backup.sh       # make a backup of the current database now
```

### Set up web server

I use nginx + gunicorn, with systemd to manage it.
You could use anything else if you want though.
Note the systemd service paths may be different for your distribution.

#### `/etc/systemd/system/sourcecatcher.service`

This service runs Sourcecatcher

```systemd
[Unit]
Description=Gunicorn instance to serve sourcecatcher
After=network.target

[Service]
User=YOUR_USER
Group=www-data
WorkingDirectory=/PATH/TO/sourcecatcher
Environment="PATH=/PATH/TO/sourcecatcher/sourcecatcher_venv/bin:/usr/bin"
ExecStart=/PATH/TO/sourcecatcher/sourcecatcher_venv/bin/gunicorn -c gunicorn.config.py -w 9 -b unix:sourcecatcher.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

#### `/etc/systemd/system/sourcecatcher_update.service`

This service updates Sourcecatcher with new tweets

```systemd
[Unit]
Description=Update sourcecatcher
After=network.target

[Service]
User=YOUR_USER
Group=www-data
WorkingDirectory=/PATH/TO/sourcecatcher
Environment="PATH=/PATH/TO/sourcecatcher/sourcecatcher_venv/bin:/home/YOUR_USER/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/bin/bash /PATH/TO/sourcecatcher/update.sh

[Install]
WantedBy=sourcecatcher_update.timer
```


#### `/etc/systemd/system/sourcecatcher_update.timer`

Periodically update Sourcecatcher

```systemd
[Unit]
Description=update sourcecatcher

[Timer]
OnBootSec=15min
OnUnitActiveSec=2hr

[Install]
WantedBy=timers.target
```

#### Start systemd services

```bash
sudo systemctl enable --now sourcecatcher.service
sudo systemctl enable --now sourcecatcher_update.timer
```
