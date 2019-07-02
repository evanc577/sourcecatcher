from flask import Flask, flash, redirect, render_template, request, session, abort
from find_match import find, stats
import requests
import urllib
app = Flask(__name__)

@app.route('/')
def hello_world():
    link = request.args.get('link')
    basename = None
    tweet_id = None
    direct_link = None
    tweet_source = None
    embed = None
    embed2 = None
    embed3 = None

    num_photos, num_tweets, mtime= stats()

    if link is not None:
        try:
            found = map(list, zip(*find('url', link)))
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

    return render_template('test.html', link=link, direct_link=direct_link,
            tweet_source=tweet_source, embed=embed, embed2=embed2, embed3=embed3,
            num_photos=num_photos, num_tweets=num_tweets, mtime=mtime)

def get_embed(tweet_id):
    tweet_source = 'https://www.twitter.com/a/status/{}'.format(tweet_id)
    url = urllib.parse.quote(tweet_source, safe='')
    get_url = 'https://publish.twitter.com/oembed?url={}'.format(url)
    try:
        r = requests.get(url=get_url)
        html = r.json()['html']
        return html
    except:
        return None
