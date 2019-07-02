#! /bin/bash

set -e

BACKUP_DIR=backups/$(date +%s)
LIVE_DIR=live/
mkdir -p $BACKUP_DIR
mkdir -p $LIVE_DIR

cp twitter_scraper.db $BACKUP_DIR
cp phash_index.ann $BACKUP_DIR

source ./twitter_venv/bin/activate
python bot.py
python gen_phashes.py

cp twitter_scraper.db $LIVE_DIR
cp phash_index.ann $LIVE_DIR
