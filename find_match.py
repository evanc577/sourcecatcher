from sc_exceptions import *
from pathlib import Path
import PIL
from PIL import Image
from io import BytesIO
from annoy import AnnoyIndex
from sc_helpers import download_content
import imagehash
import argparse
import sys
import requests
import sqlite3
import os
import time
import functools

Image.warnings.simplefilter('error', Image.DecompressionBombWarning)

def find(location, path):
    """find the closest images to an image

    Given a path or a url to an image, returns the closest matches
    (phash hamming distance)

    Arguments:
    location: 'url' or 'path'
    path: the actual url or path to the image
    """

    # load database and annoy index
    index = AnnoyIndex(64, metric='hamming')
    index.load('live/phash_index.ann')
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    # load the requested image
    img = load_image(location, path)


    start_time = time.time()

    # get the image's phash
    phash = imagehash.phash(img)
    phash_arr = phash.hash.flatten()

    # find the closest matches
    n = 16
    n_trees = index.get_n_trees()
    ann_start_time = time.time()
    annoy_results = index.get_nns_by_vector(phash_arr, n, include_distances=True, search_k=100*n*n_trees)
    ann_end_time = time.time()

    # look up the location of the match and its tweet info
    results = []
    for idx, score in map(list, zip(*annoy_results)):
        # only keep close enough matches
        if score > 8:
            break

        # find respective image in database
        c.execute('SELECT path, filename FROM hashes WHERE idx=(?)', (idx,))
        dirname, basename = c.fetchone()
        c.execute('SELECT id FROM info WHERE filename=(?) AND path=(?)', (basename, dirname))
        tweet_id = c.fetchone()
        tweet_id = tweet_id[0]
        results.append((score, tweet_id, basename))

    conn.close()

    # sort results
    results = sorted(results, key=lambda x: (-x[0], x[1]))

    end_time = time.time()

    print(results)
    print(f"total search time (phash): {end_time - start_time:06f} seconds")
    print(f"annoy search time (phash): {ann_end_time - ann_start_time:06f} seconds")

    return results


def load_image(location, path):
    """Load the user requested image"""

    if location == 'url':
        content = download_content(path)

        try:
            img = Image.open(BytesIO(content))
        except IOError:
            raise InvalidImage
    else:
        try:
            img = Image.open(path)
        except IOError as e:
            raise InvalidImage

    # check if GIF is not animated
    try:
        if img.is_animated:
            raise AnimatedGIFError
    except AttributeError:
        pass

    return img


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find a close image match")
    parser.add_argument('location', help='location of image', nargs=1, choices=('url', 'file'))
    parser.add_argument('path', help='url or path', nargs=1)
    args = parser.parse_args()

    find(args.location[0], args.path[0])

