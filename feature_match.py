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
import pickle
from sklearn.cluster import MiniBatchKMeans
from annoy import AnnoyIndex

detector = cv2.ORB_create()
computer = cv2.xfeatures2d.FREAK_create()
matcher = cv2.BFMatcher(cv2.NORM_L2)
bow_extract = cv2.BOWImgDescriptorExtractor(computer, matcher) 

# Feature extractor
def extract_features(f, des_length=128):
    try:
        idx = f[0]
        path = f[1]
        print(f'idx={idx:08d} path={path}')

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

def compute_histograms(f):
    try:
        idx = f[0]
        path = f[1][0]
        des = f[1][1]
        print(f'idx={idx:08d} path={path}')
        hist = np.zeros(dictionary.shape[0], dtype=np.float32)
        for d in des:
            cur_min_val = np.inf
            cur_min = 0
            for i,cluster in enumerate(dictionary):
                dist = np.linalg.norm(d - cluster)
                if dist < cur_min_val:
                    cur_min_val = dist
                    cur_min = i

            hist[cur_min] = hist[cur_min] + 1

        return idx, path, hist
    except Exception as e:
        print(e)
        return e


def run():
    conn = sqlite3.connect('working/twitter_scraper.db')
    c = conn.cursor()

    done_descriptors = set()
    descriptors = {}
    try:
        with open('working/descriptors.pkl', 'rb') as f:
            descriptors = pickle.load(f)
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
        
    new_descriptors = {}
    with Pool(processes=cpu_count()//2) as pool:
        for r in pool.imap(extract_features, files, chunksize=64):
            if not isinstance(r, Exception):
                descriptors[r[1]] = r[2]
                new_descriptors[r[1]] = r[2]

    with open('working/descriptors.pkl', 'wb') as f:
        pickle.dump(descriptors, f)

    try:
        with open('working/kmeans.pkl', 'rb') as f:
            kmeans = pickle.load(f)
    except:
        kmeans = MiniBatchKMeans(n_clusters=16, batch_size=128)

    for i,des in enumerate(new_descriptors.items()):
        if des[1] is not None:
            print(f'calculating kmeans, image: {i:08d}')
            kmeans = kmeans.partial_fit(np.float32(des[1]))

    with open('working/kmeans.pkl', 'wb') as f:
        pickle.dump(kmeans, f)

    global dictionary
    dictionary = np.uint8(kmeans.cluster_centers_)
    print(dictionary)
    print(dictionary.shape)
    bow_extract.setVocabulary(dictionary)

    c.execute('SELECT path, filename FROM info')
    all_images = c.fetchall()
    files = []
    for f in all_images:
        fullpath = os.path.join(f[0], f[1])
        if fullpath in descriptors:
            files.append((fullpath, descriptors[fullpath]))
    max_idx = len(files)
    print(max_idx)
    BOW_annoy_map = {}
    enum_files = enumerate(files)
    for i,f in enum_files:
        BOW_annoy_map[i] = f[0]

    index = AnnoyIndex(dictionary.shape[0], 'angular')

    files = enumerate(files)
    with Pool(processes=cpu_count()) as pool:
        for r in pool.imap(compute_histograms, files, chunksize=64):
            if not isinstance(r, Exception):
                index.add_item(r[0], r[2])
        
    index.build(20)
    index.save('working/BOW_index.ann')

    with open('working/BOWDictionary.pkl', 'wb') as f:
        pickle.dump(dictionary, f)
    with open('working/BOW_annoy_map', 'wb') as f:
        pickle.dump(BOW_annoy_map, f)


run()
