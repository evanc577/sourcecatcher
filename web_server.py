from flask import Flask, flash, redirect, render_template, request, session, abort
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from find_match import find, stats
from sc_exceptions import *
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
import requests
import urllib
import os
import random
import re
from collections import OrderedDict
from bs4 import BeautifulSoup
import tldextract
import yaml
import tweepy
from html import escape

UPLOAD_FOLDER = 'uploads'
try:
    os.mkdir(UPLOAD_FOLDER)
except:
    pass
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["10 per minute", "1 per second"],
)


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

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_secret)

api = tweepy.API(auth)

tweepy_kwargs = {
        'compression': False,
        'tweet_mode': 'extended',
        'trim_user': False,
        'include_entities': True,
        }

@app.errorhandler(HTTPException)
@limiter.exempt
def handle_exception(e):
    """Generic http error handler"""
    num_photos, num_tweets, mtime= stats()

    if request.full_path == '/' or request.full_path == '/?':
        kwargs = {
                'num_photos': num_photos,
                'num_tweets': num_tweets,
                'mtime': mtime,
                }
        return render_template('sourcecatcher.html', **kwargs)

    print(e)

    error_msg = f'<div class="error_code">{e.code} {e.name}</div><br>{e.description}'
    kwargs = {
            'embed': None,
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            'app': False,
            'app_direct_image': False,
            'results': True,
            'error_msg': error_msg,
            }
    return render_template('error.html', **kwargs)

@app.errorhandler(413)
@limiter.exempt
def entity_too_large(e):
    """Error page if uploaded file is too large"""
    num_photos, num_tweets, mtime= stats()

    kwargs = {
            'embed': None,
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            'app': False,
            'app_direct_image': False,
            'results': True,
            'error_msg': EntityTooLarge().__str__(),
            }
    return render_template('error.html', **kwargs)


@app.route('/upload', methods=['POST'])
def upload():
    f = request.files['file']
    filename = '{:016x}'.format(random.randint(0, 1<<128))
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    f.save(path)
    html = find_and_render('file', path)

    # remove old files
    uploads = ['{}/{}'.format(app.config['UPLOAD_FOLDER'], n) for n in os.listdir(app.config['UPLOAD_FOLDER'])]
    files = sorted(uploads, key=os.path.getctime)
    if len(files) > 128:
        os.remove(files[0])

    return html


@app.route('/')
@limiter.exempt
def root():
    num_photos, num_tweets, mtime= stats()
    kwargs = {
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            }
    return render_template('sourcecatcher.html', **kwargs)


@app.route('/link')
def link():
    url = request.args.get('url')
    return find_and_render('url', url)


def dc_app(path):
    """Get HQ pictures from DC app"""
    # request DC app webpage
    try:
        response = requests.get(path, timeout=30)
    except requests.exceptions.MissingSchema:
        path = 'https://' + path
        response = requests.get(path, timeout=30)

    if response.status_code != 200:
        print(response.status_code)
        error_msg = 'Error: Invalid Dreamcatcher app link'
        raise InvalidDCAppLink

    # find all images from app post
    app = True
    source = response.text
    parsed_html = BeautifulSoup(source, features='html.parser')
    images_html = ''.join([str(h) for h in parsed_html.body.find_all('div', attrs={'class': 'img-box'})])
    x = re.findall(r"((http://|https://)?file\.candlemystar\.com/cache/.*(_\d+x\d+)\.\w+)", images_html)

    # create urls for full-size images
    files = []
    for url in x:
        temp = url[0]
        temp = temp.replace('cache/', '')
        temp = temp.replace('thumb-', '')
        temp = temp.replace(url[2], '')
        files.append(temp)

    # find post username and text
    app_poster = parsed_html.body.find('div', attrs={'class': 'card-name'}).text.strip()
    app_text = parsed_html.body.find('div', attrs={'class': 'card-text'}).text.strip()
    app_images = list(OrderedDict.fromkeys(files))

    kwargs = {}
    kwargs['app_images'] = app_images
    kwargs['app_poster'] = app_poster
    kwargs['app_text'] = app_text
    kwargs['url'] = path

    return render_template('dc_app.html', **kwargs)

def dc_app_image(path):
    """Get HQ version of DC app picture"""
    # verify link
    x = re.match(r"((http://|https://)?file\.candlemystar\.com/cache/.*(_\d+x\d+)\.\w+$)", path)
    if x is None:
        raise FullSizeDCAppImage
    else:
        # get full size image
        image_link = path.replace('cache/', '')
        image_link = image_link.replace('thumb-', '')
        image_link = image_link.replace(x.groups()[2], '')

        # request image link
        if False:
            try:
                response = requests.get(image_link, timeout=30)
            except requests.exceptions.MissingSchema:
                image_link = 'https://' + image_link
                response = requests.get(image_link, timeout=30)

            if response.status_code == 200:
                app_direct_image = True
            else:
                error_msg = 'Error: Image could not be found'
                raise InvalidDCAppLink


        app_images = f'<img class="app_img" src={image_link}>\n'

        kwargs = {}
        kwargs['image_link'] = image_link
        kwargs['url'] = path

        return render_template('dc_app_image.html', **kwargs)


def find_and_render(location, path):
    """Try to find a matching image and render the results webpage"""
    app = False
    app_direct_image = False
    basename = None
    tweet_id = None
    tweets = []
    error_msg = None

    num_photos, num_tweets, mtime= stats()

    try:
        if location == 'url':
            extract = tldextract.extract(path)

            if extract.subdomain == 'dreamcatcher' and \
                    extract.domain == 'candlemystar' and \
                    extract.suffix == 'com':
                return dc_app(path)
            elif extract.subdomain == 'file' and \
                    extract.domain == 'candlemystar' and \
                    extract.suffix == 'com':
                return dc_app_image(path)
            else:
                found = find('url', path)

        elif location == 'file':
            found = find('file', path)

        id_set = set()
        count = 0
        for candidate in found:
            score, tweet_id, basename = candidate
            if tweet_id in id_set:
                continue

            score_percent = calc_score_percent(score)

            tweets.append(get_custom_embed(tweet_id, score_percent))

            id_set.add(tweet_id)
            count += 1

        if count == 0:
            raise NoMatchesFound

    except SCError as e:
        error_msg = str(e)
        print(e)

    except Exception as e:
        error_msg = "An unknown error occurred"
        print(e)

    kwargs = {
            'tweets': tweets,
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            'error_msg': error_msg,
            }

    if location == 'url':
        kwargs['url'] = path

    # found some matches
    if len(tweets) != 0:
        return render_template('match_results.html', **kwargs)

    # did not find any matches
    return render_template('error.html', **kwargs)

def get_custom_embed(tweet_id, score):
    """
    Create a custom embedded tweet
    """

    tweet = {}
    tweet['custom'] = True
    tweet['tweet_id'] = tweet_id
    tweet['score'] = score
    try:
        # get tweet contents
        status = api.get_status(tweet_id, **tweepy_kwargs)

        # process tweet text
        display_range = status._json['display_text_range']
        tweet['text_html'] = status._json['full_text'][display_range[0]:display_range[1]]

        # process name
        tweet['screen_name'] = status._json['user']['screen_name']
        tweet['identity_name'] = status._json['user']['name']
        tweet['profile_image'] = status._json['user']['profile_image_url_https']

        # process time
        tweet['ts'] = status._json['created_at']

        # process tweet images
        media = status._json['extended_entities']['media']
        tweet['num_media'] = len(media)
        images = []
        for m in media:
            images.append(m['media_url_https'])
        tweet['images'] = images

        return tweet
    except Exception as e:
        # custom embed failed for some reason, try Twitter's official embed
        print(f"Error creating custom embedded tweet: {e}")
        return get_embed(tweet_id)

def get_embed(tweet_id):
    """get html for an embedded tweet"""
    tweet = {}
    tweet['custom'] = False
    tweet_source = 'https://www.twitter.com/a/status/{}'.format(tweet_id)
    url = urllib.parse.quote(tweet_source, safe='')
    get_url = 'https://publish.twitter.com/oembed?url={}'.format(url)

    r = requests.get(url=get_url, timeout=30)
    tweet['embed_tweet'] = r.json()['html']
    return tweet

def calc_score_percent(score):
    """calculate the percentage score, where 100 is best and 0 is worst"""
    if score > 32:
        return 0

    return int(100 - 100 * score / 32)
