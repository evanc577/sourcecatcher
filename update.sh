#! /bin/bash

set -e

BACKUP_DIR=backups/$(date +%s)
mkdir -p $BACKUP_DIR
cp twitter_scraper.db $BACKUP_DIR
cp phash_index.ann $BACKUP_DIR

source ./twitter_venv/bin/activate
python bot.py
python gen_phashes.py
