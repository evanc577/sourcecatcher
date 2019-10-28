import numpy as np
import cv2
import os
import sys
import pickle
from annoy import AnnoyIndex


def image_detect_and_compute(img_name):
    """Detect and compute interest points and their descriptors."""
    detector = cv2.ORB_create()
    computer = cv2.xfeatures2d.FREAK_create()
    img = cv2.imread(img_name)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kp = detector.detect(img, None)
    kp = sorted(kp, key=lambda x: -x.response)[:2048]
    kp, des = computer.compute(img, kp)


    with open('working/kmeans.pkl', 'rb') as f:
        kmeans = pickle.load(f)

    indices = kmeans.predict(des)
    hist = np.zeros(dictionary.shape[0], dtype=np.float32)
    for i in indices:
        hist[i] = hist[i] + 1

    return hist
    

def find_similar(img_path):
    global dictionary

    with open('working/BOW_dictionary.pkl', 'rb') as f:
        dictionary = pickle.load(f)
    with open('working/BOW_annoy_map.pkl', 'rb') as f:
        annoy_map = pickle.load(f)

    index = AnnoyIndex(dictionary.shape[0], 'angular')
    index.load('working/BOW_index.ann')

    hist = image_detect_and_compute(img_path)

    n = 16
    annoy_results = index.get_nns_by_vector(hist, n, include_distances=True)
    print(annoy_results)
    for i,idx in enumerate(annoy_results[0]):
        print(annoy_map[idx], annoy_results[1][i])

find_similar(sys.argv[1])
