from pathlib import Path
from PIL import Image
from io import BytesIO
from annoy import AnnoyIndex
import imagehash
import argparse
import sys
import requests
import sqlite3
import os
import time
from datetime import datetime

def find(location, path):
    index = AnnoyIndex(64, metric='hamming')
    index.load('live/phash_index.ann')

    if location == 'url':
        MAX_DOWNLOAD = 15 * 1024 * 1024
        response = requests.get(path, stream=True)
        size = 0
        content = bytearray()
        for chunk in response.iter_content(1024):
            size += len(chunk)
            content += chunk
            if size > MAX_DOWNLOAD:
                raise ValueError
        img = Image.open(BytesIO(content))
    else:
        img = Image.open(path)

    phash = imagehash.phash(img)
    phash_arr = phash.hash.flatten()

    results = index.get_nns_by_vector(phash_arr, 16, include_distances=True)

    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    basenames = []
    tweet_ids = []

    first = True
    for idx, score in map(list, zip(*results)):
        if not first and score > 8:
            break
        first = False

        print('score: {}'.format(score))
        c.execute('SELECT path, filename FROM annoy WHERE idx=(?)', (idx,))
        dirname, basename = c.fetchone()
        fullpath = os.path.join(dirname, basename)
        c.execute('SELECT id FROM info WHERE filename=(?) AND path=(?)', (basename, dirname))
        tweet_id = c.fetchone()[0]

        print('local path:   {}'.format(fullpath))
        print('direct link:  https://pbs.twimg.com/media/{}'.format(basename))
        print('source tweet: https://www.twitter.com/statuses/{}'.format(tweet_id))
        print()

        basenames.append(basename)
        tweet_ids.append(tweet_id)

    conn.close()
    return basenames, tweet_ids

def stats():
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    c.execute('SELECT COUNT() FROM info')
    num_photos = c.fetchone()[0]

    c.execute('SELECT COUNT() FROM tweet_text')
    num_tweets = c.fetchone()[0]

    mtime = datetime.utcfromtimestamp(os.path.getmtime('phash_index.ann'))
    now = datetime.utcnow()
    time_diff = secs_to_str((now - mtime).seconds)

    conn.close()
    return num_photos, num_tweets, time_diff

def secs_to_str(secs):
    SECS_PER_MIN = 60
    SECS_PER_HR = SECS_PER_MIN * 60
    SECS_PER_DAY = SECS_PER_HR * 24

    if secs < SECS_PER_MIN:
        if secs == 1:
            return '1 second'
        else:
            return '{} seconds'.format(secs)
    if secs < SECS_PER_HR:
        mins = secs // SECS_PER_MIN
        if mins == 1:
            return '1 minute'
        else:
            return '{} minutes'.format(mins)
    if secs < SECS_PER_DAY:
        hrs = secs // SECS_PER_HR
        if hrs == 1:
            return '1 hour'
        else:
            return '{} hours'.format(hrs)
    days = secs // SECS_PER_DAY
    if days == 1:
        return '1 day'
    else:
        return '{} days'.format(secs // SECS_PER_DAY)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find a close image match")
    parser.add_argument('location', help='location of image', nargs=1, choices=('url', 'file'))
    parser.add_argument('path', help='url or path', nargs=1)
    args = parser.parse_args()

    find(args.location[0], args.path[0])

