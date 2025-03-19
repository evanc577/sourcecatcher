from multiprocessing import Pool, TimeoutError, cpu_count
from pathlib import Path
from PIL import Image
from annoy import AnnoyIndex
from sc_helpers import *
import imagehash
import os
import yaml
import sqlite3
import numpy as np
import sys
import sqlite3

def calc_phash(files):
    """calculate the phash of a image"""
    i = files[0]    # annoy index
    filename = os.path.join(files[1][0], files[1][1])

    phash = imagehash.phash(Image.open(filename))
    # print('file #{:08d}, phash: {}, filename: {}'.format(i, str(phash), filename))

    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)

    return basename, dirname, i, str(phash)


def gen_phash():
    """calculate the phashes of all images, insert into a searchable database"""

    # parse config.yaml
    try:
        path = config_file_path()
        with open(path) as f:
            config = yaml.safe_load(f)
    except IOError:
        print("error loading config file")
        sys.exit(1)

    index = AnnoyIndex(64, metric='hamming')

    # set up database
    conn = sqlite3.connect(os.path.join(base_path(), 'working/twitter_scraper.db'))
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS hashes (filename text, path text, idx int32, hash text, UNIQUE (idx))')

    # find previously hashed files
    c.execute('SELECT path, filename FROM hashes')
    done_hashes = set(c.fetchall())
    print('current hashed files: {}'.format(len(done_hashes)))

    # get next starting index
    c.execute('SELECT idx FROM hashes ORDER BY idx DESC LIMIT 1')
    cur_max_id = c.fetchone()
    if cur_max_id is None:
        next_id = 0
    else:
        next_id = cur_max_id[0] + 1

    try:
        num_cpus = config['cpus']
    except KeyError:
        num_cpus = cpu_count()

    # calculate phash of new images
    c.execute('SELECT path, filename FROM info')
    files = set(c.fetchall()) - done_hashes
    print('files to hash: {}'.format(len(files)))
    files = enumerate(files, next_id)
    with Pool(processes=num_cpus) as pool:
        for r in pool.imap(calc_phash, files, chunksize=64):
            try:
                c.execute('INSERT INTO hashes VALUES (?,?,?,?)', (r[0], r[1], r[2], r[3]))
            except sqlite3.IntegrityError:
                pass
    print("finished hashing files")

    # insert hashes into annoy
    c.execute('SELECT idx,hash from hashes')
    hashes = c.fetchall()
    for h in hashes:
        # calculate hash array
        h_int = int(h[1], 16)
        h_arr = [None] * 64
        for i in range(64):
            h_arr[63 - i] = h_int & (1 << i) != 0

        # insert hash into annoy
        index.add_item(h[0], h_arr)

    conn.commit()

    index.build(50)
    index.save(os.path.join(base_path(), 'working/phash_index.ann'))


if __name__ == '__main__':
    gen_phash()
