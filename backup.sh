#! /bin/bash

set -e

BACKUP_DIR=backups/$(date +%s)
LIVE_DIR=live
mkdir -p $BACKUP_DIR
cp $LIVE_DIR/twitter_scraper.db $BACKUP_DIR
cp $LIVE_DIR/phash_index.ann $BACKUP_DIR
