from multiprocessing import Pool, TimeoutError, cpu_count
import numpy as np
import cv2
import matplotlib.pyplot as plt
import sys
import os
import scipy
import scipy.spatial
import random
from matplotlib.pyplot import imread
import sqlite3
from PIL import Image
import nmslib

# Feature extractor
def extract_features(f, vector_size=32):
    try:
        idx = f[0]
        path = os.path.join(f[1][0], f[1][1])
        image = np.array(Image.open(path))

        # Initialize FAST and FREAK
        fast = cv2.FastFeatureDetector_create()
        freak = cv2.xfeatures2d.FREAK_create()
        kaze = cv2.KAZE_create()

        # Finding image keypoints
        kps = kaze.detect(image)

        # Getting first 32 of them. 
        kps = sorted(kps, key=lambda x: -x.response)[:vector_size]

        # computing descriptors vector
        kps, dsc = kaze.compute(image, kps)

        # Flatten all of them in one big vector - our feature vector
        dsc = dsc.flatten()

        # Making descriptor of same size
        # Descriptor vector size is 64
        needed_size = (vector_size * 64)
        if dsc.size < needed_size:
            # if we have less the 32 descriptors then just adding zeros at the
            # end of our feature vector
            dsc = np.concatenate([dsc, np.zeros(needed_size - dsc.size)])

        return f[1][1], f[1][0], idx, dsc

    except Exception as e:
        print(e)
        return e


def batch_extractor(images_path, pickled_db_path="features.pck"):
    files = [os.path.join(images_path, p) for p in sorted(os.listdir(images_path))]

    result = {}
    for f in files:
        print('Extracting features from image %s' % f)
        name = f.split('/')[-1].lower()
        result[name] = extract_features(f)


def run():
    conn = sqlite3.connect('working/twitter_scraper.db')
    c = conn.cursor()

    c.execute('CREATE TABLE IF NOT EXISTS features (filename text, path text, idx int32, UNIQUE (idx))')

    nmslib_index = nmslib.init(method='hnsw', space='cosinesimil')
    nmslib_index.loadIndex('working/features.nmslib')

    # find previously hashed files
    c.execute('SELECT path, filename FROM features')
    done_hashes = set(c.fetchall())

    c.execute('SELECT idx FROM features ORDER BY idx DESC LIMIT 1')
    cur_max_id = c.fetchone()
    if cur_max_id is None:
        next_id = 0
    else:
        next_id = cur_max_id[0] + 1

    # calculate phash of new images
    c.execute('SELECT path, filename FROM info')
    files = set(c.fetchall()) - done_hashes
    print('files to hash: {}'.format(len(files)))
    files = enumerate(files)
        
    rs = []
    with Pool(processes=cpu_count()) as pool:
        for r in pool.imap(extract_features, files, chunksize=64):
            if not isinstance(r, Exception):
                print('OKAY')
                try:
                    filepath = os.path.join(r[0], r[1])
                    print(f'{r[2]:08d} - {filepath}')
                    c.execute('INSERT INTO features VALUES (?,?,?)', (r[0], r[1], r[2],))
                    rs.append(r)
                except sqlite3.IntegrityError:
                    pass
            else:
                print('EXCEPTION')

    conn.commit()

    for r in rs:
        nmslib_index.addDataPoint(r[2], r[3])

    M = 30
    efC = 1000
    num_threads = cpu_count()
    index_time_params = {'M': M, 'indexThreadQty': num_threads, 'efConstruction': efC, 'post': 0}

    nmslib_index.createIndex(index_time_params, print_progress=True)
    nmslib_index.saveIndex('working/features.nmslib')

    sys.exit(0)

    images_path = 'resources/images/'
    files = [os.path.join(images_path, p) for p in sorted(os.listdir(images_path))]
    # getting 3 random images 
    sample = random.sample(files, 3)
    
    batch_extractor(images_path)

run()
