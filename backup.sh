#! /bin/bash

set -e

LOCK=/tmp/sourcecatcher.lock
function cleanup {
  rm -rf $LOCK
}
trap cleanup EXIT
echo "acquiring lock"
while ! mkdir $LOCK 2> /dev/null; do
  sleep 1
done
echo "acquired lock"

BACKUP_FILE=backups/$(date --iso-8601=seconds)
LIVE_DIR=live

tar -cv config.yaml $LIVE_DIR/twitter_scraper.db $LIVE_DIR/phash_index.ann $LIVE_DIR/descriptors.pkl $LIVE_DIR/BOW_annoy_map.pkl $LIVE_DIR/kmeans.pkl $LIVE_DIR/BOW_index.ann 2>/dev/null | pigz > $BACKUP_FILE.tar.gz

echo "Backed up to $BACKUP_FILE.tar.gz"

./prune_backups.sh
