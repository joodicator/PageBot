from itertools import *
from collections import defaultdict
import traceback
import urllib2
import time
import ssl
import re

import util
import imgur
import message
import url_collect

MIRROR_HOSTS = (
    'i*.4cdn.org',
    'i*.photobucket.com',
    '*.fjcdn.com',
    '*i*.tinypic.com',
)

CACHE_SIZE = 1024
REPEAT_S = 60*60*3

link, install, uninstall = util.LinkSet().triple()

mirror_hosts_re = re.compile(
    '^(%s)$' % '|'.join(util.wc_to_re(h, anchor=False) for h in MIRROR_HOSTS))

ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

chan_times = defaultdict(dict)
cache_old = dict()
cache_new = dict()

def reload(prev):
    if hasattr(prev, 'chan_times') and isinstance(prev.chan_times, dict):
        chan_times.update(prev.chan_times)
    if hasattr(prev, 'cache_old') and isinstance(prev.cache_old, dict):
        cache_old.update(prev.cache_old)
    if hasattr(prev, 'cache_new') and isinstance(prev.cache_new, dict):
        cache_new.update(prev.cache_new)

def get_cache(key):
    return cache_new.get(key) \
        or cache_old.get(key)

def put_cache(key, value):
    global cache_old, cache_new
    if key not in cache_new and len(cache_new) >= CACHE_SIZE:
        cache_old = cache_new
        cache_new = dict()    
    cache_new[key] = value

def get_mirror_url(url, chan):
    # Ensure that this URL is supposed to be mirrored.
    match = url_collect.URL_PART_RE.match(url)
    if not match: return
    pref,host,suff,path,frag = match.group('pref','host','suff','path','frag')
    pref,host = pref.lower(),host.lower()
    if not mirror_hosts_re.match(host): return
    if not re.search(r'\.(png|jpe?g|gif)$', path): return

    normal_url = ''.join((pref, host, suff, path, frag))

    # Ensure this URL has not been used too recently in this channel.
    times = chan_times[chan.lower()]
    now = time.time()
    for time_url, time_s in times.items():
        if time_s + REPEAT_S < now: del times[time_url]
    if normal_url in times: return
    times[normal_url] = now
    
    # Try to obtain from cache.
    mirror_url = get_cache(normal_url)
    if mirror_url: return mirror_url

    # Otherwise, upload to imgur.com.
    try:
        res = imgur.upload_url(url)
    except imgur.ImgurError:
        traceback.print_exc()
        return
    except urllib2.URLError:
        traceback.print_exc()
        return

    mirror_url = res.get('link')
    if mirror_url: put_cache(normal_url, mirror_url)

    return mirror_url

@link('URL_COLLECT_URLS', 'URL_CMD_URLS')
def h_url_collect_urls(bot, urls, chan, id, orig_msg):
    if not chan: return
    chan = chan.lower()
    delete_indices = []

    for url_spec, index in izip(urls, count()):
        url, is_nsfw = url_nsfw(url_spec)
        mirror_url = get_mirror_url(url, chan)
        if not mirror_url: continue

        nsfw_str = '\2NSFW:\2 ' if is_nsfw else ''
        msg = '%s%s copied to <%s>.' % (nsfw_str, url, mirror_url)
        message.reply(bot, id, chan, msg, prefix=False)
        url_collect.history[chan].append([nsfw_url(mirror_url, is_nsfw)])
        delete_indices.append(index)

    new_urls = [u for (i,u) in izip(count(),urls) if i not in delete_indices]
    for index in xrange(len(url_collect.history[chan])-1, -1, -1):
        if url_collect.history[chan][index] == urls:
            if new_urls:
                url_collect.history[chan][index] = new_urls
            else:
                del url_collect.history[chan][index]
            break

# ('NSFW',url) -> (url,True); url -> (url,False)
def url_nsfw(spec):
    return (spec[1],True) \
        if type(spec) is tuple and spec[0] == 'NSFW' \
      else (spec, False)

# (url,True) -> ('NSFW',url); (url,False) -> url
def nsfw_url(url, is_nsfw):
    return ('NSFW',url) if is_nsfw else url
