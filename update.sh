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

LIVE_DIR=live/
WORKING_DIR=working
mkdir -p $LIVE_DIR
mkdir -p $WORKING_DIR

rm -rf $WORKING_DIR/*

echo "copying to working directory"
cp $LIVE_DIR/twitter_scraper.db $WORKING_DIR
cp $LIVE_DIR/phash_index.ann $WORKING_DIR

source ./sourcecatcher_venv/bin/activate
echo "starting ingest"
python bot.py
echo "starting phash"
python gen_phashes.py

echo "moving to live directory"
mv -f $WORKING_DIR/twitter_scraper.db $LIVE_DIR
mv -f $WORKING_DIR/phash_index.ann $LIVE_DIR

echo "update complete"
