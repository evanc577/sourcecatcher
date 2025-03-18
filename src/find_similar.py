import numpy as np
import cv2
import os
import sys
import pickle
from annoy import AnnoyIndex
import sqlite3
from find_match import download_content
from sc_helpers import *
import joblib
import time


def image_detect_and_compute(img_name, location='file'):
    """Detect and compute interest points and their descriptors."""
    detector = cv2.ORB_create()
    computer = cv2.xfeatures2d.FREAK_create()

    # load image
    if location == 'file':
        img = cv2.imread(img_name)
    elif location == 'url':
        content = np.asarray(download_content(img_name))
        img = cv2.imdecode(content, cv2.IMREAD_UNCHANGED)

    # compute descriptors
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kp = detector.detect(img, None)
    kp = sorted(kp, key=lambda x: -x.response)[:2048]
    kp, des = computer.compute(img, kp)

    # calculate histogram
    indices = kmeans.predict(des)
    hist = np.zeros(kmeans.cluster_centers_.shape[0], dtype=np.float32)
    for i in indices:
        hist[i] = hist[i] + 1

    return hist
    

def find_similar(img_path, location='file'):
    print(img_path)
    global kmeans

    # load files
    annoy_map = joblib.load(os.path.join(base_path(), 'live/BOW_annoy_map.pkl'))
    kmeans = joblib.load(os.path.join(base_path(), 'live/kmeans.pkl'))

    index = AnnoyIndex(kmeans.n_clusters, 'angular')
    index.load(os.path.join(base_path(), 'live/BOW_index.ann'))

    conn = sqlite3.connect(os.path.join(base_path(), 'live/twitter_scraper.db'))
    c = conn.cursor()

    # compute histogram
    start_time = time.time()
    try:
        hist = image_detect_and_compute(img_path, location=location)
    except cv2.error:
        return []


    # find most similar images
    n = 12
    n_trees = index.get_n_trees()
    ann_start_time = time.time()
    annoy_results = index.get_nns_by_vector(hist, n, include_distances=True, search_k=-1)
    ann_end_time = time.time()

    # process results
    results = []
    max_score = -1
    for i,idx in enumerate(annoy_results[0]):
        # discard bad results
        if annoy_results[1][i] > 1.0:
            break

        score = int(100 * (1 - annoy_results[1][i]))
        if i == 0:
            max_score = score
        elif max_score - score > 10:
            break

        # get tweet info
        path = annoy_map[idx]
        basename = os.path.basename(path)
        dirname = os.path.dirname(path)
        c.execute('SELECT id FROM info WHERE filename=(?) AND path=(?)', (basename, dirname))
        tweet_id = c.fetchone()[0]
        tup = (score, tweet_id, basename,)
        results.append(tup)

    end_time = time.time()

    print(results)
    print(f"total search time (cbir): {end_time - start_time:06f} seconds")
    print(f"annoy search time (cbir): {ann_end_time - ann_start_time:06f} seconds")

    return results

if __name__ == "__main__":
    find_similar(sys.argv[2], location=sys.argv[1])
