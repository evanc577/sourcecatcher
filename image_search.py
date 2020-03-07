from datetime import timedelta, datetime
from find_match import find
from find_similar import find_similar
from flask import render_template
from sc_exceptions import *
from sc_helpers import render_page
import os
import re
import requests
import requests_cache
import sqlite3
import sys
import tweepy
import urllib
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
    access_token = config['access_token']
    access_secret = config['access_secret']
    consumer_key = config['consumer_key']
    consumer_secret = config['consumer_secret']
except KeyError:
    print("could not parse config file")
    sys.exit(1)

# set up tweepy
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)
api = tweepy.API(auth)
tweepy_kwargs = {
        'compression': False,
        'tweet_mode': 'extended',
        'trim_user': False,
        'include_entities': True,
        }

# cache http requests
req_expire_after = timedelta(seconds=600)
cached_req_session = requests_cache.CachedSession('sc_cache', backend='sqlite', expire_after=req_expire_after)


def image_search(location, path, found, content=None):
    tweet_ids = []
    tweets = []
    warning_msg = None

    id_score = {}
    count = 0
    for candidate in found:
        score, tweet_id, basename = candidate
        if tweet_id in id_score:
            continue

        score_percent = calc_score_percent(score)

        tweet_ids.append(str(tweet_id))
        id_score[tweet_id] = score_percent
        count += 1

    if count == 0:
        # try content-based search if no matches are found
        if location == 'url':
            found = find_similar(path, location='url', content=content)
        elif location == 'file':
            found = find_similar(path, location='file')
        count = 0
        for candidate in found:
            score, tweet_id, basename = candidate
            if tweet_id in id_score:
                continue

            tweet_ids.append(str(tweet_id))
            id_score[tweet_id] = score
            count += 1

        if count == 0:
            raise NoMatchesFound
        else:
            warning_msg = "No exact matches found<br /><strong>Experimental:</strong> Showing close matches"

    if len(tweet_ids) != 0:
        tweepy_kwargs = {
                'tweet_mode': 'extended',
                }

        todo_ids = set()
        for tweet_id in tweet_ids:
            todo_ids.add(tweet_id.strip())

        # create tweet cards
        try:
            lookedup_tweets = sorted(api.statuses_lookup(tweet_ids, **tweepy_kwargs),
                    key=lambda x: (-id_score[x._json['id']], x._json['id']))
            for lookedup_tweet in lookedup_tweets:
                lookedup_tweet = lookedup_tweet._json
                score = id_score[lookedup_tweet['id']]
                tweets.append(get_custom_embed(lookedup_tweet, score))
                try:
                    todo_ids.remove(str(lookedup_tweet['id']))
                except KeyError:
                    pass
        except tweepy.RateLimitError as e:
            for tweet_id in tweet_ids:
                tweets.append(get_embed(tweet_id))
                try:
                    todo_ids.remove(str(lookedup_tweet['id']))
                except KeyError:
                    pass

        # add tweets that have been removed
        for tweet_id in todo_ids:
            tweets.append(get_saved_tweet(tweet_id, id_score[int(tweet_id)]))

    # show error if no tweets are found
    if len(tweets) == 0:
        raise NoMatchesFound

    kwargs = {
            'tweets': tweets,
            'warning_msg': warning_msg,
            'page_title': 'Search',
            }

    if location == 'url':
        kwargs['url'] = path

    return render_page('match_results.html', **kwargs)


def get_saved_tweet(tweet_id, score):
    """
    Create tweet embed from saved data
    """
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    tweet = {}
    tweet['custom'] = True
    tweet['is_backup'] = True
    tweet['score'] = score
    tweet['tweet_id'] = tweet_id

    c.execute('SELECT * FROM tweet_text where id=(?)', (tweet_id,))
    _, text = c.fetchone()
    tweet['text_html'] = re.sub(r"https://t\.co/\w+$", "", text)

    images = []
    c.execute('SELECT * FROM info where id=(?)', (tweet_id,))
    info = c.fetchone()
    tweet['screen_name'] = info[2]

    return tweet


def get_custom_embed(lookedup_tweet, score):
    """
    Create a custom embedded tweet
    """

    tweet = {}
    tweet['custom'] = True
    tweet['tweet_id'] = lookedup_tweet['id']
    tweet['score'] = score

    # process tweet text
    display_range = lookedup_tweet['display_text_range']
    tweet['text_html'] = lookedup_tweet['full_text'][display_range[0]:display_range[1]]

    # process name
    tweet['screen_name'] = lookedup_tweet['user']['screen_name']
    tweet['identity_name'] = lookedup_tweet['user']['name']
    tweet['profile_image'] = lookedup_tweet['user']['profile_image_url_https']

    # process time
    tweet['ts'] = lookedup_tweet['created_at']

    # process tweet images
    media = lookedup_tweet['extended_entities']['media']
    tweet['num_media'] = len(media)
    images = []
    for m in media:
        images.append(m['media_url_https'])
    tweet['images'] = images

    return tweet

def get_embed(tweet_id):
    """get html for an embedded tweet"""
    tweet = {}
    tweet['custom'] = False
    tweet_source = 'https://www.twitter.com/a/status/{}'.format(tweet_id)
    url = urllib.parse.quote(tweet_source, safe='')
    get_url = 'https://publish.twitter.com/oembed?url={}'.format(url)

    r = cached_req_session.get(url=get_url, timeout=30)
    tweet['embed_tweet'] = r.json()['html']
    return tweet

def calc_score_percent(score):
    """calculate the percentage score, where 100 is best and 0 is worst"""
    if score > 32:
        return 0

    return int(100 - 100 * score / 32)
