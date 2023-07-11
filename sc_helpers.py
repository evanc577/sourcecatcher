from datetime import datetime
from flask import render_template, make_response
from sc_exceptions import *
import os
import requests
import sqlite3
import yaml


def render_page(template, code=200, **kwargs):
    """Get stats and render template"""
    num_photos, mtime = stats()
    kwargs['num_photos'] = num_photos
    kwargs['mtime'] = mtime
    news = get_news()
    if news is not None:
        kwargs["news"] = news

    resp = make_response(render_template(template, **kwargs), code)
    return resp


def get_news():
    try:
        dirpath = os.path.dirname(os.path.realpath(__file__))
        path = os.path.join(dirpath, 'config.yaml')
        with open(path) as f:
            config = yaml.safe_load(f)
    except IOError:
        return None

    try:
        return config["news"]
    except KeyError:
        return None


def stats():
    """returns stats for the database"""
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    c.execute('SELECT MAX(_ROWID_) FROM info LIMIT 1')
    num_photos = c.fetchone()[0]

    mtime = datetime.utcfromtimestamp(os.path.getmtime('live/twitter_scraper.db'))
    now = datetime.utcnow()
    time_diff = secs_to_str((now - mtime).seconds)

    conn.close()
    return num_photos, time_diff


def secs_to_str(secs):
    """converts number of seconds to a human readable string"""
    SECS_PER_MIN = 60
    SECS_PER_HR = SECS_PER_MIN * 60
    SECS_PER_DAY = SECS_PER_HR * 24

    if secs < SECS_PER_MIN:
        if secs == 1:
            return '1 second'
        else:
            return '{} seconds'.format(secs)
    if secs < SECS_PER_HR:
        mins = secs // SECS_PER_MIN
        if mins == 1:
            return '1 minute'
        else:
            return '{} minutes'.format(mins)
    if secs < SECS_PER_DAY:
        hrs = secs // SECS_PER_HR
        if hrs == 1:
            return '1 hour'
        else:
            return '{} hours'.format(hrs)
    days = secs // SECS_PER_DAY
    if days == 1:
        return '1 day'
    else:
        return '{} days'.format(secs // SECS_PER_DAY)


def download_content(url):
    MAX_DOWNLOAD = 15 * 1024 * 1024
    try:
        headers = {"User-Agent": "Sourcecatcher"}
        response = requests.get(url, headers=headers, stream=True, timeout=30)
    except requests.exceptions.MissingSchema as e:
        try:
            # try https
            response = requests.get("https://" + url, stream=True, timeout=30)
        except requests.RequestException as e:
            try:
                # try http
                response = requests.get("http://" + url, stream=True, timeout=30)
            except requests.RequestException as e:
                raise InvalidLink
    except requests.exceptions.RequestException as e:
        raise InvalidLink

    if not response.ok:
        raise InvalidLink

    size = 0
    content = bytearray()
    for chunk in response.iter_content(1024):
        size += len(chunk)
        content += chunk
        if size > MAX_DOWNLOAD:
            raise EntityTooLarge

    return content
