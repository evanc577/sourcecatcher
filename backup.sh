#! /bin/bash

set -e

if [ -z "$BACKUP_SERVER" ]; then
  echo "BACKUP_SERVER unset"
  exit 1
fi
if [ -z "$BACKUP_SERVER_USER" ]; then
  echo "BACKUP_SERVER_USER unset"
  exit 1
fi
if [ -z "$BACKUP_SERVER_PASS" ]; then
  echo "BACKUP_SERVER_PASS unset"
  exit 1
fi

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

BACKUP_FILE=$(date --iso-8601=seconds).tar.gz
LIVE_DIR=live

tar -cv config.yaml $LIVE_DIR/twitter_scraper.db $LIVE_DIR/phash_index.ann $LIVE_DIR/descriptors.bdb $LIVE_DIR/BOW_annoy_map.pkl $LIVE_DIR/kmeans.pkl $LIVE_DIR/BOW_index.ann 2>/dev/null \
  | pigz \
  | curl -T - -u "$BACKUP_SERVER_USER:$BACKUP_SERVER_PASS" -H "X-FILE: $BACKUP_FILE" $BACKUP_SERVER

echo "Backed up to $BACKUP_SERVER"
