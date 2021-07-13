from datetime import timedelta, datetime
from dcapp import dc_app, get_video_link
from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from image_search import image_search, image_search_cache
from sc_exceptions import *
from sc_helpers import render_page
from werkzeug.exceptions import HTTPException
import hashlib
import os
import random
import redis
import requests_cache
import sqlite3
import sys
import tldextract
import traceback
import urllib
import yaml

UPLOAD_FOLDER = 'uploads'
VIDEOS_FOLDER = 'dcapp_videos'
try:
    os.mkdir(UPLOAD_FOLDER)
except:
    pass
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['VIDEOS_FOLDER'] = VIDEOS_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

redis_db = redis.Redis(host='localhost', port=6379, db=0)

def urlescape(url):
    return urllib.parse.quote(url, safe='')

# calculate sha256 hash for file
def sha256(filename):
    filename = os.getcwd() + filename
    with open(filename,"rb") as f:
        bytes = f.read() # read entire file as bytes
        return hashlib.sha256(bytes).hexdigest()

app.jinja_env.globals.update(sha256=sha256)
app.jinja_env.globals.update(urlescape=urlescape)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    #  default_limits=["30 per minute", "1 per second"],
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

req_expire_after = timedelta(seconds=600)
cached_req_session = requests_cache.CachedSession('sc_cache', backend='sqlite', expire_after=req_expire_after)

@app.after_request
def add_header(response):
    if response.mimetype == 'text/html':
        response.cache_control.public = True
        response.cache_control.max_age = 300 # 5 minutes
        response.cache_control.must_revalidate = True
        pass
    else:
        response.cache_control.public = True
        response.cache_control.max_age = 2678400 # 31 days
        response.cache_control.must_revalidate = False
    return response


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Generic http error handler"""
    if request.full_path == '/' or request.full_path == '/?':
        return render_page('sourcecatcher.html')

    print(e)

    error_msg = f'<div class="error_code">{e.code} {e.name}</div><br>{e.description}'
    kwargs = {
            'embed': None,
            'app': False,
            'app_direct_image': False,
            'results': True,
            'error_msg': error_msg,
            'page_title': 'Error',
            }
    return render_page('error.html', code=e.code, **kwargs)

@app.errorhandler(413)
def entity_too_large(e):
    """Error page if uploaded file is too large"""
    kwargs = {
            'app': False,
            'app_direct_image': False,
            'results': True,
            'error_msg': EntityTooLarge().__str__(),
            'page_title': 'Error',
            }
    return render_page('error.html', **kwargs)


@app.route('/api/get_dcapp_video')
def api_get_dcapp_video():
    url = request.args.get('url')
    if url is None:
        return (jsonify({'reason': 'no url specified'}), 400)
    try:
        filename = get_video_link(url)
        return send_from_directory(app.config['VIDEOS_FOLDER'], filename)
    except VideoDownloadError:
        return (jsonify({'reason': 'could not download video'}), 404)


@app.route('/upload', methods=['POST'])
@limiter.limit("30/minute, 1/second")
def upload():
    # remove old requests from cache
    cached_req_session.cache.remove_old_entries(datetime.now() - req_expire_after)

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
def root():
    # remove old requests from cache
    cached_req_session.cache.remove_old_entries(datetime.now() - req_expire_after)

    return render_page('sourcecatcher.html')


@app.route('/link')
@limiter.limit("30/minute, 1/second")
def link():
    url = request.args.get('url')
    return find_and_render('url', url)


@app.route('/twitter_users')
def twitter_users():
    """Show list of indexed twitter users"""
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()

    # get all users
    c.execute('SELECT user FROM users')
    users = c.fetchall()

    # get deleted users
    try:
        c.execute('SELECT user FROM deleted_users')
        deleted_users = [x[0] for x in c.fetchall()]
    except:
        deleted_users = []

    c.close()

    # combine users and deleted users
    users = [(tup[0], tup[0] not in deleted_users) for tup in sorted(users)]

    user_count = len(users)
    kwargs = {
            'users': users,
            'user_count': user_count,
            'page_title': 'Indexed Twitter Users',
            }

    return render_page('twitter_users.html', **kwargs)


def find_and_render(location, path):
    """Try to find a matching image and render the results webpage"""
    error_msg = None
    error_reasons = None
    error_link = None
    warning_msg = None
    code = 200

    try:
        # return error if url is for DC app
        if location == 'url':
            extract = tldextract.extract(path)
            if extract.subdomain == 'dreamcatcher' and \
                    extract.domain == 'candlemystar' and \
                    extract.suffix == 'com':
                raise SCError('DC App has closed and is no longer supported')
                #  return dc_app(path)

        # clear image_search() lru cache if database was updated
        db_mtime = os.path.getmtime('live/twitter_scraper.db')
        if redis_db.get("db_mtime") != bytes(str(db_mtime), "utf-8"):
            print("clearing image_search() cache")
            image_search_cache.clear()
        redis_db.set("db_mtime", str(db_mtime))

        # find matching results
        ret_kwargs = image_search(location, path)

        return render_page('match_results.html', **ret_kwargs)

    except TWError as e:
        error_msg = str(e)
        error_link = e.link
        print(e)

    except NoMatchesFound as e:
        error_msg = str(e)
        error_reasons = e.reasons()
        code = 404
        print(e)

    except SCError as e:
        error_msg = str(e)
        code = 400
        print(e)

    except Exception as e:
        error_msg = "An unknown error occurred"
        traceback.print_exc()
        code = 500
        print(e)

    kwargs = {
            'error_msg': error_msg,
            'error_reasons': error_reasons,
            'error_link': error_link,
            'warning_msg': warning_msg,
            'page_title': 'Error',
            'code': code,
            }

    if location == 'url':
        kwargs['url'] = path

    # did not find any matches
    return render_page('error.html', **kwargs)
