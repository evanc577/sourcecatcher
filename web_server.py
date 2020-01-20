from bs4 import BeautifulSoup
from datetime import timedelta, datetime
from dcapp import dc_app
from find_match import find
from find_similar import find_similar
from flask import Flask, flash, redirect, render_template, request, session, abort, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from image_search import image_search
from sc_exceptions import *
from sc_helpers import download_content
from sc_helpers import render_page
from download_dcapp_video import get_video_link
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
import hashlib
import os
import random
import requests
import requests_cache
import sqlite3
import tldextract
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

# calculate sha256 hash for file
def sha256(filename):
    filename = os.getcwd() + filename
    with open(filename,"rb") as f:
        bytes = f.read() # read entire file as bytes
        return hashlib.sha256(bytes).hexdigest();

app.jinja_env.globals.update(sha256=sha256)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["30 per minute", "1 per second"],
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

@app.errorhandler(HTTPException)
@limiter.exempt
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
            }
    return render_page('error.html', **kwargs)

@app.errorhandler(413)
@limiter.exempt
def entity_too_large(e):
    """Error page if uploaded file is too large"""
    kwargs = {
            'app': False,
            'app_direct_image': False,
            'results': True,
            'error_msg': EntityTooLarge().__str__(),
            }
    return render_page('error.html', **kwargs)


@app.route('/api/get_dcapp_video')
def api_get_dcapp_video():
    dcapp_id = request.args.get('id')
    if dcapp_id is None:
        return (jsonify({'reason': 'no id specified'}), 400)
    try:
        filename = get_video_link(dcapp_id)
        return send_from_directory(app.config['VIDEOS_FOLDER'], filename)
    except VideoDownloadError:
        return (jsonify({'reason': 'could not download video'}), 404)


@app.route('/upload', methods=['POST'])
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
@limiter.exempt
def root():
    # remove old requests from cache
    cached_req_session.cache.remove_old_entries(datetime.now() - req_expire_after)

    return render_page('sourcecatcher.html')


@app.route('/link')
def link():
    url = request.args.get('url')
    return find_and_render('url', url)


@app.route('/twitter_users')
@limiter.exempt
def users():
    """Show list of indexed twitter users"""
    conn = sqlite3.connect('live/twitter_scraper.db')
    c = conn.cursor()
    c.execute('SELECT user FROM users')
    users = c.fetchall()
    c.close()
    users = [tup[0] for tup in sorted(users)]
    user_count = len(users)
    kwargs = {
            'users': users,
            'user_count': user_count,
            }

    return render_page('twitter_users.html', **kwargs)


<<<<<<< Updated upstream
=======
def dc_app(path):
    """Get HQ pictures from DC app"""

    # get id
    x = re.search(r'dreamcatcher\.candlemystar\.com\/post\/(\d+)', path)
    dcapp_id = x.group(1)

    # request DC app webpage
    try:
        try:
            response = cached_req_session.get(path, timeout=30)
        except requests.exceptions.MissingSchema:
            path = 'https://' + path
            response = cached_req_session.get(path, timeout=30)
    except requests.exceptions.Timeout:
        raise DCAppError('Request timed out')

    if response.status_code != 200:
        raise DCAppError(f'Error code {response.status_code}')

    app_images = None
    app_video = None
    app_video_poster = None

    source = response.text
    parsed_html = BeautifulSoup(source, features='html.parser')

    # match image urls
    regex = r"((http://|https://)?file\.candlemystar\.com/cache/.*(_\d+x\d+)\.\w+)"

    try:
        # try to find video
        app_video = parsed_html.body.find('video').find('source').attrs['src']
        app_video_poster = parsed_html.body.find('video').attrs['poster']
    except:
        # find all images from app post
        images_html = ''.join([str(h) for h in parsed_html.body.find_all('div', attrs={'class': 'img-box'})])
        x = re.findall(regex, images_html)

        # create urls for full-size images
        files = []
        for url in x:
            temp = url[0]
            temp = temp.replace('cache/', '')
            temp = temp.replace('thumb-', '')
            temp = temp.replace(url[2], '')
            files.append(temp)

        # remove duplicates
        app_images = list(OrderedDict.fromkeys(files))

    # find post username and text
    app_poster = parsed_html.body.find('div', attrs={'class': 'card-name'}).text.strip()
    app_text = parsed_html.body.find('div', attrs={'class': 'card-text'}).text.strip()

    # find profile picture
    profile_pic = parsed_html.body.find('div', attrs={'class': 'profile-img'}).find('img').attrs['src']
    try:
        x = re.findall(regex, profile_pic)[0]
        temp = x[0]
        temp = temp.replace('cache/', '')
        temp = temp.replace('thumb-', '')
        temp = temp.replace(x[2], '')
        profile_pic = temp
    except Exception as e:
        print(f"Error getting full size profile picture {e}")

    kwargs = {}
    kwargs['app_video'] = app_video
    kwargs['app_video_poster'] = app_video_poster
    kwargs['app_images'] = app_images
    kwargs['app_poster'] = app_poster
    kwargs['app_text'] = app_text
    kwargs['profile_pic'] = profile_pic
    kwargs['url'] = path
    kwargs['dcapp_id'] = dcapp_id

    return render_page('dc_app.html', **kwargs)

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
                response = cached_req_session.get(image_link, timeout=30)
            except requests.exceptions.MissingSchema:
                image_link = 'https://' + image_link
                response = cached_req_session.get(image_link, timeout=30)

            if response.status_code == 200:
                app_direct_image = True
            else:
                error_msg = 'Error: Image could not be found'
                raise InvalidDCAppLink


        app_images = f'<img class="app_img" src={image_link}>\n'

        kwargs = {}
        kwargs['image_link'] = image_link
        kwargs['url'] = path

        return render_page('dc_app_image.html', **kwargs)


def find_and_render(location, path):
    """Try to find a matching image and render the results webpage"""
    app = False
    app_direct_image = False
    basename = None
    content = None
    error_msg = None
    error_reasons = None
    error_link = None
    warning_msg = None

    try:
        if location == 'url':
            extract = tldextract.extract(path)
            if extract.subdomain == 'dreamcatcher' and \
                    extract.domain == 'candlemystar' and \
                    extract.suffix == 'com':
                return dc_app(path)
            else:
                content = download_content(path)
                found = find('url', path, content=content)

        elif location == 'file':
            found = find('file', path)

        return image_search(location, path, found, content=content)

    except TWError as e:
        error_msg = str(e)
        error_link = e.link
        print(e)

    except NoMatchesFound as e:
        error_msg = str(e)
        error_reasons = e.reasons()
        print(e)

    except SCError as e:
        error_msg = str(e)
        print(e)

    except Exception as e:
        error_msg = "An unknown error occurred"
        print(e)

    kwargs = {
            'error_msg': error_msg,
            'error_reasons': error_reasons,
            'error_link': error_link,
            'warning_msg': warning_msg,
            }

    if location == 'url':
        kwargs['url'] = path

    # did not find any matches
    return render_page('error.html', **kwargs)
