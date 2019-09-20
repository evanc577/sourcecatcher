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

UPLOAD_FOLDER = 'uploads'
try:
    os.mkdir(UPLOAD_FOLDER)
except:
    pass
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024


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
        print(uploads)
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

def find_and_render(location, path):
    app = False
    basename = None
    tweet_id = None
    direct_link = None
    tweet_source = None
    embed = None
    embed2 = None
    embed3 = None

    num_photos, num_tweets, mtime= stats()

    if path is not None:
        try:
            if location == 'url':
                domain = urllib.parse.urlparse(path).hostname
                if 'dreamcatcher.candlemystar.com' == domain:
                    app = True

                    # find all images from app post
                    source = requests.get(path).text
                    x = re.findall(r"https://file\.candlemystar\.com/cache/post.*400x400\.\w+", source)
                    files = []
                    for url in x:
                        temp = url.replace('cache/', '')
                        temp = temp.replace('thumb-', '')
                        temp = temp.replace('_400x400', '')
                        files.append(temp)

                    # find post username and text
                    parsed_html = BeautifulSoup(source, features='html.parser')
                    app_poster = parsed_html.body.find('div', attrs={'class': 'card-name'}).text.strip()
                    app_text = parsed_html.body.find('div', attrs={'class': 'card-text'}).text.strip()
                else:
                    found = map(list, zip(*find('url', path)))
            elif location == 'file':
                found = map(list, zip(*find('file', path)))

            if not app:
                id_set = set()
                count = 0
                for candidate in found:
                    basename, tweet_id = candidate
                    if tweet_id in id_set:
                        continue

                    direct_link = 'https://pbs.twimg.com/media/{}'.format(basename)
                    tweet_source = 'https://www.twitter.com/statuses/{}'.format(tweet_id)

                    if count == 0:
                        embed = get_embed(tweet_id)
                    elif count == 1:
                        embed2 = get_embed(tweet_id)
                    elif count == 2:
                        embed3 = get_embed(tweet_id)

                    id_set.add(tweet_id)
                    count += 1
        except Exception as e:
            print(e)

    kwargs = {
            'direct_link': direct_link,
            'tweet_source': tweet_source,
            'embed': embed,
            'embed2': embed2,
            'embed3': embed3,
            'num_photos': num_photos,
            'num_tweets': num_tweets,
            'mtime': mtime,
            'app': app,
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


    if path is not None:
        kwargs['nothing'] = True

    return render_template('test.html', **kwargs)

def add_result_title(html, tweet_source):
    header = '<div class="result">\n<div class="result_title">\n<a href={0} ">{0}</a>'.format(tweet_source)
    footer = '\n</div>'
    return header + html + footer

def get_embed(tweet_id):
    """get html for an embedded tweet"""
    tweet_source = 'https://www.twitter.com/a/status/{}'.format(tweet_id)
    url = urllib.parse.quote(tweet_source, safe='')
    get_url = 'https://publish.twitter.com/oembed?url={}'.format(url)
    try:
        r = requests.get(url=get_url)
        html = r.json()['html']
        return html
    except:
        return None

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
