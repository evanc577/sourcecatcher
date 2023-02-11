from datetime import datetime
from email.utils import parsedate_tz, mktime_tz
from multiprocessing.pool import ThreadPool
from PIL import Image
from threading import Lock
import json
import os
import piexif
import requests
import shutil
import sqlite3
import subprocess
import sys
import yaml

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
                                (filename, path, tweet['user']['screen_name'], tweet['id_str']))
                    except sqlite3.IntegrityError:
                        pass

    try:
        if 'full_text' in tweet:
            text_field = 'full_text'
        else:
            text_field = 'text'

        with lock:
            c.execute('INSERT INTO tweet_text VALUES (?,?)', (tweet['id_str'], tweet[text_field]))

        # add hashtags
        with lock:
            for hashtag in tweet['entities']['hashtags']:
                c.execute('INSERT INTO hashtags VALUES (?,?)', (hashtag['text'], tweet['id_str']))
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

    conn = sqlite3.connect('working/twitter_scraper.db', check_same_thread=False)
    c = conn.cursor()
    with lock:
        c.execute('CREATE TABLE IF NOT EXISTS users (user text, last_id int64, UNIQUE (user))')
        c.execute('CREATE TABLE IF NOT EXISTS info (filename text, path text, user text, id int64, UNIQUE (filename, path))')
        c.execute('CREATE INDEX IF NOT EXISTS id ON info(id)')
        c.execute('CREATE TABLE IF NOT EXISTS tweet_text (id int64, text text, UNIQUE (id))')
        c.execute('CREATE TABLE IF NOT EXISTS hashtags (hashtag text, id int64, UNIQUE (hashtag, id))')
        c.execute('CREATE TABLE IF NOT EXISTS deleted_users (user text, UNIQUE (user))')

    for user in users:
        print('Checking {} for new tweets'.format(user))
        user = user.lower()
        # find the last read tweet
        with lock:
            c.execute('SELECT last_id FROM users WHERE user=?', (user,))
        last_id = c.fetchone()
        first_id = None

        # Call tweet-scraper
        process_args: list[str] = ["tweet-scraper", f"from:{user} filter:images"]
        if last_id is not None:
            last_id = last_id[0]
            process_args.extend(["--min-id", str(last_id + 1)])
        else:
            last_id = 0
        process = subprocess.Popen(process_args, stdout=subprocess.PIPE)

        with ThreadPool(20) as pool:
            for tweet in pool.imap(download_tweet, map(json.loads, process.stdout)):
                assert str(tweet["id"]) == tweet["id_str"]
                last_id = max(last_id, int(tweet["id_str"]))
        # update last tweet read
        with lock:
            try:
                c.execute('INSERT INTO users VALUES (?,?)', (user, last_id))
            except sqlite3.IntegrityError:
                c.execute('UPDATE users SET last_id=(?) WHERE user=(?)', (last_id ,user))
            conn.commit()
