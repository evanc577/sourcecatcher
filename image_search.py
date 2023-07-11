from cachetools import cached, LRUCache
from cachetools.keys import hashkey
from datetime import timedelta, datetime
from find_match import find
from sc_exceptions import *
import hashlib
import os
import re
import requests_cache
import sqlite3
import sys
import yaml

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
    temp = config['priority_users']
    num_prio_users = len(temp)
    priority_users = {}
    for i in range(num_prio_users):
        priority_users[temp[i].casefold()] = i
except (KeyError, TypeError):
    num_prio_users = 0
    priority_users = {}

# cache http requests
req_expire_after = timedelta(seconds=600)
cached_req_session = requests_cache.CachedSession('sc_cache', backend='sqlite', expire_after=req_expire_after)

# image search cache
image_search_cache = LRUCache(maxsize=128)
def image_search_key(location, path):
    if location == "file":
        with open(path, "rb") as f:
            bytes = f.read() # read entire file as bytes
            return hashlib.sha256(bytes).hexdigest()
    return hashkey(path)


@cached(cache=image_search_cache, key=image_search_key)
def image_search(location, path):
    tweet_ids = []
    tweets = []
    warning_msg = None
    id_score = {}
    count = 0

    # try phash search first
    found = find(location, path)
    for score, tweet_id, basename in found:
        if tweet_id in id_score:
            continue

        score_percent = calc_score_percent(score)

        tweet_ids.append(str(tweet_id))
        id_score[tweet_id] = score_percent
        count += 1

    # show error if no results are found
    if count == 0:
        raise NoMatchesFound

    # add tweets that have been removed
    for tweet_id in tweet_ids:
        tweets.append(get_saved_tweet(tweet_id, id_score[int(tweet_id)]))

    # limit each twitter user to 3 tweets
    user_count = {}
    temp = []
    for tweet in tweets:
        if tweet['screen_name'].casefold() not in user_count:
            user_count[tweet['screen_name'].casefold()] = 0
        if user_count[tweet['screen_name'].casefold()] >= 3:
            continue
        user_count[tweet['screen_name'].casefold()] += 1
        temp.append(tweet)
    tweets = temp

    # show error if no tweets are found
    if len(tweets) == 0:
        raise NoMatchesFound

    # sort tweets by score then by id (date)
    tweets.sort(key=lambda tweet: (priority(tweet['screen_name']), -min(90, tweet['score']), tweet['tweet_id']))

    kwargs = {
            'tweets': tweets,
            'warning_msg': warning_msg,
            'page_title': 'Search',
            }

    if location == 'url':
        kwargs['url'] = path

    return kwargs

def priority(user):
    """
    return the priority if the given twitter user based on config file
    """

    if user.casefold() in priority_users:
        return priority_users[user.casefold()]

    return num_prio_users


def get_saved_tweet(tweet_id, score):
    """
    Create tweet embed from saved data
    """
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    tweet = {}
    tweet['custom'] = True
    tweet['is_backup'] = False
    tweet['score'] = score
    tweet['tweet_id'] = int(tweet_id)

    # calculate timestamp from id
    ts = id2ts(tweet_id)
    tweet['ts'] = datetime.utcfromtimestamp(ts).isoformat() + "+00:00"

    # Set text
    c.execute('SELECT * FROM tweet_text where id=(?)', (tweet_id,))
    _, text = c.fetchone()
    tweet['text_html'] = re.sub(r"https://t\.co/\w+$", "", text)

    c.execute('SELECT * FROM info where id=(?)', (tweet_id,))
    info = [x for x in c.fetchall()]

    # Set screen_name
    tweet['screen_name'] = info[0][2]

    # Add images
    tweet["images"] = [f"https://pbs.twimg.com/media/{x[0]}" for x in info]
    tweet["num_media"] = len(info)

    return tweet

def calc_score_percent(score):
    """calculate the percentage score, where 100 is best and 0 is worst"""
    if score > 32:
        return 0

    return int(100 - 100 * score / 32)

def id2ts(tweet_id):
    return ((int(tweet_id)>>22) + 1288834974657) / 1000
