from bs4 import BeautifulSoup
from collections import OrderedDict
from datetime import timedelta, datetime
from sc_exceptions import *
from sc_helpers import render_page
import multiprocessing
import os
import re
import requests
import requests_cache
import youtube_dl
import redis

# process synchronization for video download
lck = multiprocessing.Lock()
cv = multiprocessing.Condition(lck)
WORKING = 'sc_working_videos'
r = redis.Redis(host='localhost', port=6379, db=0)
r.delete(WORKING)

req_expire_after = timedelta(seconds=600)
cached_req_session = requests_cache.CachedSession('sc_cache', backend='sqlite', expire_after=req_expire_after)


def get_parsed_html(path):
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

    source = response.text
    return BeautifulSoup(source, features='html.parser')


def find_video(parsed_html):
    # try to find video
    return parsed_html.body.find('video').find('source').attrs['src']


def extract_id(url):
    # extract id
    x = re.search(r"dreamcatcher\.candlemystar\.com\/post\/(\d+)", url)
    if x:
        return x.group(1)
    return None


def dc_app(path):
    """Get HQ pictures from DC app"""
    parsed_html = get_parsed_html(path)

    app_images = None
    app_video = None
    app_video_poster = None
    dcapp_id = extract_id(path)

    # match image urls
    regex = r"((http://|https://)?file\.candlemystar\.com/cache/.*(_\d+x\d+)\.\w+)"

    try:
        # try to find video
        app_video = find_video(parsed_html)
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
    kwargs['dcapp_id'] = dcapp_id
    kwargs['app_video'] = app_video
    kwargs['app_video_poster'] = app_video_poster
    kwargs['app_images'] = app_images
    kwargs['app_poster'] = app_poster
    kwargs['app_text'] = app_text
    kwargs['profile_pic'] = profile_pic
    kwargs['url'] = path

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


def get_video_link(url):
    # extract id
    dcapp_id = extract_id(url)
    if dcapp_id is None:
        raise VideoDownloadError

    # find m3u8 url
    try:
        video_url = find_video(get_parsed_html(url))
    except Exception as e:
        print(e)
        raise VideoDownloadError

    filename = f"{dcapp_id}.mp4"
    path = f'dcapp_videos/{filename}'
    temppath = f'{path}.temp'

    with cv:
        while r.sismember(WORKING, dcapp_id):
            if not cv.wait(timeout=30):
                raise VideoDownloadError
        r.sadd(WORKING, dcapp_id)

    if not os.path.exists(path):
        opts = {
           'outtmpl': temppath,
           'noplaylist' : True,
        }
        try:
            with youtube_dl.YoutubeDL(opts) as ydl:
                result = ydl.download([video_url])
        except youtube_dl.utils.DownloadError as e:
            raise VideoDownloadError 

        os.rename(temppath, path)

    with cv:
        r.srem(WORKING, dcapp_id)
        cv.notify_all()

    return filename
