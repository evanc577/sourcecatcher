from flask import Flask, flash, redirect, render_template, request, session, abort
from find_match import find, stats
from werkzeug.utils import secure_filename
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

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        f = request.files['file']
        filename = '{:016x}'.format(random.randint(0, 1<<128))
        if f.filename == '':
            flash('No selected file')
            return redirect(request.url)
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        f.save(path)
        html = find_and_render('file', path)

        # remove old files
        uploads = ['{}/{}'.format(app.config['UPLOAD_FOLDER'], n) for n in os.listdir(app.config['UPLOAD_FOLDER'])]
        files = sorted(uploads, key=os.path.getctime)
        if len(files) > 128:
            os.remove(files[0])

        return html
    else:
        link = request.args.get('link')
        return find_and_render('url', link)


@app.route('/')
def root():
    link = request.args.get('link')
    return find_and_render('url', link)

def dc_app(path):
    # request DC app webpage
    try:
        response = requests.get(path)
    except requests.exceptions.MissingSchema:
        path = 'https://' + path
        response = requests.get(path)

    if response.status_code != 200:
        print(response.status_code)
        error_msg = 'Error: Invalid Dreamcatcher app link'
        raise Exception('invalid DC app link')

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

    return files, app_poster, app_text

def dc_app_image(path):
    # verify link
    x = re.match(r"((http://|https://)?file\.candlemystar\.com/cache/.*(_\d+x\d+)\.\w+$)", path)
    if x is None:
        error_msg = 'Error: Invalid Dreamcatcher app image link, or image is already full size'
        raise Exception('Error: Invalid Dreamcatcher app image link')
    else:
        # get full size image
        image_link = path.replace('cache/', '')
        image_link = image_link.replace('thumb-', '')
        image_link = image_link.replace(x.groups()[2], '')

        # request image link
        try:
            response = requests.get(image_link)
        except requests.exceptions.MissingSchema:
            image_link = 'https://' + image_link
            response = requests.get(image_link)

        if response.status_code == 200:
            app_direct_image = True
        else:
            error_msg = 'Error: Image could not be found'
            raise Exception('invalid url')

        return image_link


def find_and_render(location, path):
    app = False
    app_direct_image = False
    basename = None
    tweet_id = None
    embed = None
    error_msg = 'Error: Could not analyze image'

    num_photos, num_tweets, mtime= stats()


    if path is not None:
        try:
            if location == 'url':
                extract = tldextract.extract(path)

                if extract.subdomain == 'dreamcatcher' and \
                        extract.domain == 'candlemystar' and \
                        extract.suffix == 'com':
                    files, app_poster, app_text = dc_app(path)
                    app = True
                elif extract.subdomain == 'file' and \
                        extract.domain == 'candlemystar' and \
                        extract.suffix == 'com':
                    image_link = dc_app_image(path)
                    app_direct_image = True
                else:
                    found = find('url', path)

            elif location == 'file':
                found = find('file', path)

            if not app and not app_direct_image:
                id_set = set()
                count = 0
                for candidate in found:
                    score, tweet_id, basename = candidate
                    if tweet_id in id_set:
                        continue

                    score_percent = calc_score_percent(score)

                    if count == 0:
                        embed = get_custom_embed(tweet_id, score_percent)
                    else:
                        embed += get_custom_embed(tweet_id, score_percent)

                    id_set.add(tweet_id)
                    count += 1

                if count == 0:
                    error_msg = 'No matches found'
        except Exception as e:
            print(e)

    kwargs = {
            'embed': embed,
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            'app': app,
            'app_direct_image': app_direct_image,
            'error_msg': error_msg,
            }

    if location == 'url':
        kwargs['link'] = path

    if app:
        files = list(OrderedDict.fromkeys(files))
        app_images = ''
        app_images += f'<h3>{app_poster}:</h3>\n'
        app_images += f'<p>{app_text}<p>\n'
        for f in files:
            app_images += f'<img class="app_img" src={f}>\n'
        kwargs['app_images'] = app_images

    if app_direct_image:
        app_images = f'<img class="app_img" src={image_link}>\n'
        kwargs['app_images'] = app_images

    if path is not None:
        kwargs['nothing'] = True

    return render_template('sourcecatcher.html', **kwargs)

def add_result_title(html, tweet_source):
    header = '<div class="result">\n<div class="result_title">\n<a href={0} ">{0}</a>'.format(tweet_source)
    footer = '\n</div>'
    return header + html + footer

def get_custom_embed(tweet_id, score):
    """
    Create a custom embedded tweet
    """
    try:
        # get tweet contents
        status = api.get_status(tweet_id, **tweepy_kwargs)

        # process tweet text
        display_range = status._json['display_text_range']
        text = status._json['full_text'][display_range[0]:display_range[1]]
        text_html = escape(text).replace('\n', '<br />')

        # process name
        screen_name = status._json['user']['screen_name']
        identity_name = status._json['user']['name']
        profile_image = status._json['user']['profile_image_url_https']

        # process time
        ts = status._json['created_at']

        # process tweet images
        media = status._json['extended_entities']['media']
        num_media = len(media)
        images_html = ""
        for m in media:
            url = m['media_url_https']
            images_html += f'<div class="image_container num_media{num_media}">\n<img alt="Twitter image" src="{url}">\n</div>\n'

        html = f'''
<a class="tweet_embed" target="_blank" rel="noopener noreferrer" title="View on Twitter" href="https://twitter.com/{screen_name}/status/{tweet_id}">
  <div class="match_score">Match Score: {score}</div>
  <img class="twitter_logo" src="static/Twitter_Logo_Blue.svg">
  <div class="author">
    <img class="avatar" alt="Avatar" src="{profile_image}">
    <div class="name_container">
      <span class="identity_name">
        {identity_name}
      </span>
      <span class="screen_name">
        @{screen_name}
      </span>
    </div>
  </div>
  <div class="datetime">
    <script>datetime = new Date("{ts}");
      datestr = datetime.toLocaleDateString();
      timestr = datetime.toLocaleTimeString();
      datetimestr = timestr + " - " + datestr;
      document.write(datetimestr)
    </script>
  </div>
  <div class="tweet_text">
    {text_html}
  </div>
  <div class="tweet_images">
    {images_html}
  </div>
</a>
'''

        return html
    except Exception as e:
        # custom embed failed for some reason, try Twitter's official embed
        print(f"Error creating custom embedded tweet: {e}")
        return get_embed(tweet_id)

def get_embed(tweet_id):
    """get html for an embedded tweet"""
    tweet_source = 'https://www.twitter.com/a/status/{}'.format(tweet_id)
    url = urllib.parse.quote(tweet_source, safe='')
    get_url = 'https://publish.twitter.com/oembed?url={}'.format(url)
    try:
        r = requests.get(url=get_url)
        html = r.json()['html'] + '\n'
        return html
    except:
        return None

def calc_score_percent(score):
    """calculate the percentage score, where 100 is best and 0 is worst"""
    if score > 32:
        return 0

    return int(100 - 100 * score / 32)

def remove_scripts(html):
    """experimental: remove scripts from html"""
    begin = '<script'
    end = '</script>'
    idx1 = html.find(begin)
    if idx1 == -1:
        return html

    idx2 = html.find(end)
    if idx2 == -1:
        html = html[:idx1]
    else:
        idx2 = idx2 + len(end)
        html = html[:idx1] + html[idx2:]

    return html
