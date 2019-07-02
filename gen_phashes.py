from multiprocessing import Pool, TimeoutError, cpu_count
from pathlib import Path
from PIL import Image
from annoy import AnnoyIndex
import imagehash
import os
import yaml
import sqlite3
import numpy as np
import sys
import sqlite3

def insert_phash(files):
    i = files[0]
    filename = files[1]

    phash = imagehash.phash(Image.open(filename))
    phash_arr = phash.hash.flatten()
    print('file #{:08d}, phash: {:08x}, filename: {}'.format(i, int(str(phash), 16), filename))

    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)

    return phash_arr, basename, dirname, i


def gen_phash():
    try:
        dirpath = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(dirpath, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
    except IOError:
        print("error loading config file")
        sys.exit(1)
    try:
        access_token = config['access_token']
        access_secret = config['access_secret']
        consumer_key = config['consumer_key']
        consumer_secret = config['consumer_secret']
        users = config['users']
        media_dir = config['media_dir']
    except KeyError:
        print("could not parse users file")
        sys.exit(1)

    index = AnnoyIndex(64, metric='hamming')

    conn = sqlite3.connect('twitter_scraper.db')
    c = conn.cursor()
    c.execute('DROP TABLE IF EXISTS annoy')
    c.execute('CREATE TABLE IF NOT EXISTS annoy (filename text, path text, idx int32, UNIQUE (idx))')

    files = enumerate(Path(media_dir).glob('*/*/*.jpg'))
    num_cpus = cpu_count() // 2
    if num_cpus == 0:
        num_cpus = 1
    with Pool(processes=num_cpus) as pool:
        for r in pool.imap(insert_phash, files, chunksize=64):
            index.add_item(r[3], r[0])
            c.execute('INSERT INTO annoy VALUES (?,?,?)', (r[1], r[2], r[3]))

    conn.commit()

    index.build(20)
    index.save('phash_index.ann')


if __name__ == '__main__':
    gen_phash()
