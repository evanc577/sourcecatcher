import numpy as np
import cv2
import sys
import os
import random
import sqlite3
from PIL import Image
import nmslib

def extract_features(path, vector_size=32):
    image = np.array(Image.open(path))    
    # Initialize FAST and FREAK
    fast = cv2.FastFeatureDetector_create()
    freak = cv2.xfeatures2d.FREAK_create()

    # Finding image keypoints
    kps = fast.detect(image)

    # Getting first 32 of them. 
    kps = sorted(kps, key=lambda x: -x.response)[:vector_size]

    # computing descriptors vector
    kps, dsc = freak.compute(image, kps)

    # Flatten all of them in one big vector - our feature vector
    dsc = dsc.flatten()

    # Making descriptor of same size
    # Descriptor vector size is 64
    needed_size = (vector_size * 64)
    if dsc.size < needed_size:
        # if we have less the 32 descriptors then just adding zeros at the
        # end of our feature vector
        dsc = np.concatenate([dsc, np.zeros(needed_size - dsc.size)])

    return dsc

def find_similar(path):
    conn = sqlite3.connect('working/twitter_scraper.db')
    c = conn.cursor()

    nmslib_index = nmslib.init(method='hnsw', space='cosinesimil')
    nmslib_index.loadIndex('working/features.nmslib')
    efS = 800000
    query_time_params = {'efSearch': efS}
    nmslib_index.setQueryTimeParams(query_time_params)

    dsc = extract_features(path)

    ids, dists = nmslib_index.knnQuery(dsc, 10)
    print(ids)
    print(dists)

    for i, idx in enumerate(ids):
        c.execute('SELECT path,filename FROM features WHERE idx=(?)', (int(idx),))
        dirname, basename = c.fetchone()
        print(f'{dists[i]:05f} {os.path.join(dirname, basename)}')

if __name__ == "__main__":
    find_similar(sys.argv[1])
