from multiprocessing import Pool, TimeoutError, cpu_count
import numpy as np
import cv2
import gc
import sys
import os
import sqlite3
import pickle
from sklearn.cluster import MiniBatchKMeans
import joblib
from annoy import AnnoyIndex
import yaml
import bsddb3
from sc_helpers import config_file_path

detector = cv2.ORB_create()
computer = cv2.xfeatures2d.FREAK_create()

# Feature extractor
def extract_features(f, des_length=2048):
    """Extract features and descriptors from images"""
    try:
        idx = f[0]
        path = f[1]
        print(f'features: idx={idx:08d} path={path}')

        img = cv2.imread(path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        kp = detector.detect(img, None)
        kp = sorted(kp, key=lambda x: -x.response)
        kp, des = computer.compute(img, kp)

        des = des[0:des_length]

        return idx, path, des

    except Exception as e:
        print(e)
        return e

def compute_histograms(idx, path, descriptors):
    """Compute histograms for bag of (visual) words"""
    try:
        des = deserialize(descriptors[path.encode()])
        print(f'histograms: idx={idx:08d} path={path}')
        indices = kmeans.predict(des)
        hist = np.zeros(kmeans.cluster_centers_.shape[0], dtype=np.float32)
        for i in indices:
            hist[i] = hist[i] + 1

        return idx, path, hist
    except Exception as e:
        print(path)
        print(e)
        return e


def deserialize(s):
    return np.frombuffer(s, dtype="uint8").reshape((-1, 64))


def gen_cbir():
    """Generate structures needed for content-based image retrieval"""

    global kmeans

    # parse config.yaml
    print("parsing config")
    try:
        path = config_file_path()
        with open(path) as f:
            config = yaml.safe_load(f)
    except IOError:
        print("error loading config file")
        sys.exit(1)
    try:
        num_cpus = config['cpus']
    except KeyError:
        num_cpus = cpu_count()

    # connect to sqlite database
    print("connecting to databases")
    conn = sqlite3.connect('working/twitter_scraper.db')
    c = conn.cursor()

    # load descriptors
    descriptors = bsddb3.db.DB()
    if os.path.exists("working/descriptors.bdb"):
        descriptors.open("working/descriptors.bdb")
    else:
        descriptors.open("working/descriptors.bdb", dbtype=bsddb3.db.DB_BTREE, flags=bsddb3.db.DB_CREATE)

    # calculate descriptors of new images
    print("determine files to compute")
    c.execute('SELECT path, filename FROM info')
    files = c.fetchall()
    files = [os.path.join(a,b) for a,b in files]
    compute_files = set()
    for i,f in enumerate(files):
        if descriptors.get(f.encode()) is None:
            compute_files.add(f)
        if i % 10000 == 0:
            print(i)
    print('files to compute: {}'.format(len(compute_files)))
    files = enumerate(compute_files)

    # extract features from new images
    print("computing descriptors")
    new_descriptors = {}
    with Pool(processes=num_cpus) as pool:
        for r in pool.imap(extract_features, files, chunksize=64):
            if not isinstance(r, Exception):
                des = deserialize(r[2])
                descriptors[r[1].encode()] = des
                new_descriptors[r[1]] = des

    # create clusters
    try:
        kmeans = joblib.load('working/kmeans.pkl')
        n_clusters = kmeans.cluster_centers_.shape[0]
    except:
        n_clusters = 512
        kmeans = MiniBatchKMeans(n_clusters=n_clusters, batch_size=2048)

    # calculate kmeans
    print("calculating kmeans")
    cur = None
    for i,des in enumerate(new_descriptors.items()):
        if des[1] is not None:
            print(f'calculating kmeans, image: {i:08d}')
            if des[1].shape[0] < n_clusters:
                if cur is None:
                    cur = des[1]
                else:
                    cur = np.concatenate((cur, des[1]), axis=0)
                if cur is not None and cur.shape[0] > n_clusters:
                    kmeans = kmeans.partial_fit(np.float32(cur))
                    cur = None
            else:
                if cur is not None:
                    cur = np.concatenate((cur, des[1]), axis=0)
                    kmeans = kmeans.partial_fit(np.float32(cur))
                    cur = None
                else:
                    kmeans = kmeans.partial_fit(np.float32(des[1]))
    if cur is not None:
        kmeans = kmeans.partial_fit(np.float32(cur))

    del new_descriptors
    gc.collect()

    # save kmeans
    print("saving kmeans")
    joblib.dump(kmeans, 'working/kmeans.pkl')

    # set up structures for annoy index
    print("setting up annoy structures")
    c.execute('SELECT path, filename FROM info')
    all_images = c.fetchall()
    files = []
    for f in all_images:
        fullpath = os.path.join(f[0], f[1])
        if descriptors.get(fullpath.encode()) is not None:
            files.append(fullpath)
    BOW_annoy_map = {}
    for i,f in enumerate(files):
        BOW_annoy_map[i] = f

    index = AnnoyIndex(n_clusters, 'angular')
    index.on_disk_build('working/BOW_index.ann')

    # add histograms to annoy index
    print("computing histograms")
    for i,f in enumerate(files):
        r = compute_histograms(i, f, descriptors)
        if not isinstance(r, Exception):
            index.add_item(r[0], r[2])
    
    # build index
    print("building index")
    index.build(50)

    descriptors.sync()
    descriptors.close()

    # save index map
    print("saving annoy map")
    joblib.dump(BOW_annoy_map, 'working/BOW_annoy_map.pkl')

if __name__ == '__main__':
    gen_cbir()
