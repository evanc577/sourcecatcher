from multiprocessing import Pool, TimeoutError, cpu_count
import numpy as np
import cv2
import sys
import os
import sqlite3
import pickle
from sklearn.cluster import MiniBatchKMeans
import joblib
from annoy import AnnoyIndex
import yaml

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

def compute_histograms(idx, path, des):
    """Compute histograms for bag of (visual) words"""
    try:
        print(f'histograms: idx={idx:08d} path={path}')
        indices = kmeans.predict(des)
        hist = np.zeros(kmeans.cluster_centers_.shape[0], dtype=np.float32)
        for i in indices:
            hist[i] = hist[i] + 1

        return idx, path, hist
    except Exception as e:
        print(e)
        return e


def gen_cbir():
    """Generate structures needed for content-based image retrieval"""

    global kmeans

    # parse config.yaml
    try:
        dirpath = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(dirpath, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
    except IOError:
        print("error loading config file")
        sys.exit(1)
    try:
        num_cpus = config['cpus']
    except KeyError:
        num_cpus = cpu_count()
    try:
        recalculate_kmeans = config['recalculate_kmeans']
    except KeyError:
        recalculate_kmeans = True

    # connect to sqlite database
    conn = sqlite3.connect('working/twitter_scraper.db')
    c = conn.cursor()

    # load descriptors
    done_descriptors = set()
    descriptors = {}
    try:
        descriptors = joblib.load('working/descriptors.pkl')
        for k,v in descriptors.items():
            done_descriptors.add(k)
    except Exception as e:
        pass

    # calculate descriptors of new images
    c.execute('SELECT path, filename FROM info')
    files = c.fetchall()
    files = [os.path.join(a,b) for a,b in files]
    files = set(files) - done_descriptors
    print('files to compute: {}'.format(len(files)))
    files = enumerate(files)

    # extract features from new images
    new_descriptors = {}
    with Pool(processes=num_cpus) as pool:
        for r in pool.imap(extract_features, files, chunksize=64):
            if not isinstance(r, Exception):
                descriptors[r[1]] = r[2]
                new_descriptors[r[1]] = r[2]

    if recalculate_kmeans:
        # create clusters
        try:
            kmeans = joblib.load('working/kmeans.pkl')
            n_clusters = kmeans.cluster_centers_.shape[0]
        except:
            n_clusters = 512
            kmeans = MiniBatchKMeans(n_clusters=n_clusters, batch_size=2048)

        # calculate kmeans
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

        # save kmeans
        joblib.dump(kmeans, 'working/kmeans.pkl')
    else:
        kmeans = joblib.load('working/kmeans.pkl')
        n_clusters = kmeans.cluster_centers_.shape[0]


    # save descriptors
    joblib.dump(descriptors, 'working/descriptors.pkl')

    # set up structures for annoy index
    c.execute('SELECT path, filename FROM info')
    all_images = c.fetchall()
    files = []
    for f in all_images:
        fullpath = os.path.join(f[0], f[1])
        if fullpath in descriptors:
            files.append(fullpath)
    max_idx = len(files)
    BOW_annoy_map = {}
    enum_files = enumerate(files)
    for i,f in enum_files:
        BOW_annoy_map[i] = f

    index = AnnoyIndex(n_clusters, 'angular')

    # add histograms to annoy index
    for i,f in enumerate(files):
        r = compute_histograms(i, f, descriptors[f])
        if not isinstance(r, Exception):
            index.add_item(r[0], r[2])
    index.build(20)
    index.save('working/BOW_index.ann')

    # save index map
    joblib.dump(BOW_annoy_map, 'working/BOW_annoy_map.pkl')

if __name__ == '__main__':
    gen_cbir()
