from multiprocessing.pool import ThreadPool
from threading import Lock
import os
import numpy as np
import os
import pprint
import sqlite3
import sys
import tweepy
import yaml
from datetime import datetime
from email.utils import parsedate_tz, mktime_tz
import requests
import shutil
import piexif
from PIL import Image
import io
from itertools import islice
import time

def mkdir(time_str):
    """create a directory for a given time

    Example:
    Given 'Sat Dec 14 04:35:55 +0000 2013', creates media_dir/2013/12/
    
    Arguments:
    time_str: time string returned by twitter api
    """
    timestamp = mktime_tz(parsedate_tz(time_str))
    date = datetime.fromtimestamp(timestamp)
    year = '{:04d}'.format(date.year)
    month = '{:02d}'.format(date.month)

    path = os.path.join(media_dir, year)
    path = os.path.join(path, month)
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except FileExistsError:
            pass

    return path, date

def download_media(url, path):
    """downloads media to path"""
    filename = url.split('/')[-1]
    path = os.path.join(path, filename)

    if (os.path.exists(path)):
        print('\talready downloaded {}'.format(path))
        return filename

    for _ in range(10):
        try:
            with requests.get(url, stream=True, timeout=10) as r:
                if r.status_code != 200:
                    return None
                with open(path, 'wb') as f:
                    print('\tdownloading to {}'.format(path))
                    shutil.copyfileobj(r.raw, f)
        except requests.exceptions.Timeout:
            continue
        break

    return filename

def write_exif_date(path, filename, date):
    """write exif date to an image"""
    date_str = date.strftime('%Y:%m:%d %k:%M:%S')
    fullpath = os.path.join(path, filename)

    exif_ifd = {piexif.ExifIFD.DateTimeOriginal: date_str}
    exif_dict = {'Exif': exif_ifd}
    exif_bytes = piexif.dump(exif_dict)
    im = Image.open(fullpath)
    im.save(fullpath, exif=exif_bytes)


def download_tweet_media(tweet):
    """try to download images linked in tweet"""
    if 'extended_entities' in tweet and 'media' in tweet['extended_entities']:
        for media in tweet['extended_entities']['media']:
            print('{}/{}:'.format(tweet['user']['screen_name'], tweet['id_str']))
            if 'video_info' in media:
                return
            else:
                # tweet contains pictures
                path, date = mkdir(tweet['created_at'])
                filename = download_media(media['media_url_https'], path)
                if filename is None:
                    return
                try:
                    write_exif_date(path, filename, date)
                except OSError:
                    try:
                        os.remove(os.path.join(path, filename))
                    except:
                        pass
                    filename = download_media(media['media_url_https'], path)
                    if filename is None:
                        return

                # add info
                with lock:
                    try:
                        c.execute('INSERT INTO info VALUES (?,?,?,?)',
                                (filename, path, tweet['user']['screen_name'], tweet['id']))
                    except sqlite3.IntegrityError:
                        pass

    try:
        if 'full_text' in tweet:
            text_field = 'full_text'
        else:
            text_field = 'text'

        with lock:
            c.execute('INSERT INTO tweet_text VALUES (?,?)', (tweet['id'], tweet[text_field]))

        # add hashtags
        with lock:
            for hashtag in tweet['entities']['hashtags']:
                c.execute('INSERT INTO hashtags VALUES (?,?)', (hashtag['text'], tweet['id']))
    except sqlite3.IntegrityError:
        pass

    with lock:
        conn.commit()

def download_tweet(tweet):

    # skip if tweet is actually a retweet
    if 'retweeted_status' in tweet:
        return tweet

    # download tweet media
    download_tweet_media(tweet)

    return tweet

if __name__ == "__main__":
    pp = pprint.PrettyPrinter()

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
        users = config['users']
        media_dir = config['media_dir']
    except KeyError:
        print("could not parse users file")
        sys.exit(1)


    lock = Lock()

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_secret)

    api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)


    conn = sqlite3.connect('working/twitter_scraper.db', check_same_thread=False)
    c = conn.cursor()
    with lock:
        c.execute('CREATE TABLE IF NOT EXISTS users (user text, last_id int64, UNIQUE (user))')
        c.execute('CREATE TABLE IF NOT EXISTS info (filename text, path text, user text, id int64, UNIQUE (filename, path))')
        c.execute('CREATE TABLE IF NOT EXISTS tweet_text (id int64, text text, UNIQUE (id))')
        c.execute('CREATE TABLE IF NOT EXISTS hashtags (hashtag text, id int64, UNIQUE (hashtag, id))')
        c.execute('CREATE TABLE IF NOT EXISTS deleted_users (user text, UNIQUE (user))')

    count = 0

    # add individual tweets to database
    n = 100 # number of ids per statuses_lookup api call, 100 max
    tweepy_kwargs = {
            'tweet_mode': 'extended',
            }
    try:
        with open('add_tweets.txt', 'r') as f:
            new_tweets = False
            while True:
                ids = [x.strip() for x in islice(f, n)]
                if not ids:
                    break
                new_tweets = True
                tweets = api.statuses_lookup(ids, **tweepy_kwargs)
                tweets = [t._json for t in tweets]
                with ThreadPool(16) as pool:
                    for r in pool.imap(download_tweet_media, tweets):
                        pass
                    #  for tweet in tweets:
                        #  # download tweet media
                        #  download_tweet_media(tweet)
            if new_tweets:
                os.rename('add_tweets.txt', f'add_tweets.txt.{str(int(time.time()))}' )
    except FileNotFoundError:
        pass

    # download linked media for all users
    tweepy_kwargs = {
            'compression': False,
            'tweet_mode': 'extended',
            'count': 200,
            'exclude_replies': False,
            'include_rts': True,
            }
    for user in users:
        print('Checking {} for new tweets'.format(user))
        user = user.lower()
        # find the last read tweet
        with lock:
            c.execute('SELECT last_id FROM users WHERE user=?', (user,))
        last_id = c.fetchone()
        first_id = None
        if last_id is not None:
            first_scan = False
            last_id = last_id[0]
        else:
            first_scan = True

        # fetch tweets
        try:
            if first_scan:
                tweets = api.user_timeline(user, **tweepy_kwargs)
            else:
                tweets = api.user_timeline(user, since_id=last_id+1, **tweepy_kwargs)
            try:
                with lock:
                    c.execute('DELETE FROM deleted_users WHERE user=(?)', (user,))
                    conn.commit()
            except:
                pass
        except tweepy.error.TweepError as e:
            print("tweepy error {}".format(e))

            # 4XX response status code
            if e.response.status_code // 10 == 40:
                try:
                    with lock:
                        c.execute('INSERT INTO deleted_users VALUES (?)', (user,))
                        conn.commit()
                except:
                    pass
            continue


        num_tweets = len(tweets)
        while num_tweets > 0:
            tweets = [t._json for t in tweets]
            with ThreadPool(20) as pool:
                for tweet in pool.imap(download_tweet, tweets):
                    # update last tweet read
                    if last_id is None or tweet['id'] > last_id:
                        with lock:
                            try:
                                c.execute('INSERT INTO users VALUES (?,?)', (user, tweet['id']))
                            except sqlite3.IntegrityError:
                                c.execute('UPDATE users SET last_id=(?) WHERE user=(?)', (tweet['id'], user))
                            conn.commit()
                        last_id = tweet['id']

                    # update first tweet read
                    if first_id is None or tweet['id'] < first_id:
                        first_id = tweet['id']

            # fetch more tweets if available
            try:
                if first_scan:
                    tweets = api.user_timeline(user, max_id=first_id-1, **tweepy_kwargs)
                else:
                    tweets = api.user_timeline(user, since_id=last_id+1, **tweepy_kwargs)
            except tweepy.error.TweepError as e:
                print("tweepy error {}".format(e))
                continue
            num_tweets = len(tweets)
