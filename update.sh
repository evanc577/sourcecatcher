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

cp $LIVE_DIR/twitter_scraper.db $WORKING_DIR
cp $LIVE_DIR/phash_index.ann $WORKING_DIR
cp $LIVE_DIR/descriptors.pkl $WORKING_DIR
cp $LIVE_DIR/BOW_annoy_map.pkl $WORKING_DIR
cp $LIVE_DIR/kmeans.pkl $WORKING_DIR
cp $LIVE_DIR/BOW_index.ann $WORKING_DIR

source ./sourcecatcher_venv/bin/activate
python bot.py
python gen_phashes.py
python feature_match.py

mv -f $WORKING_DIR/twitter_scraper.db $LIVE_DIR
mv -f $WORKING_DIR/phash_index.ann $LIVE_DIR
mv -f $WORKING_DIR/descriptors.pkl $LIVE_DIR
mv -f $WORKING_DIR/BOW_annoy_map.pkl $LIVE_DIR
mv -f $WORKING_DIR/kmeans.pkl $LIVE_DIR
mv -f $WORKING_DIR/BOW_index.ann $LIVE_DIR
