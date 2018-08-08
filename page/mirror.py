from __future__ import print_function

from itertools import *
from collections import defaultdict, OrderedDict
import traceback
import urllib
import urllib2
import time
import ssl
import re
import sys
import random
import string
import httplib

from url import USER_AGENT
import util
import imgur
import message
import url_collect
import runtime

MIRROR_HOSTS = (
    'i*.4cdn.org',
    'i*.4chan.org',
    'i*.photobucket.com',
    '*.fjcdn.com',
    '*i*.tinypic.com',
)

PATH_RE = re.compile(
    r'\.(png|jpe?g|gif|webm)(~[^/]*)?$')

CACHE_SIZE = 1024
REPEAT_S = 60*60*3

UPLOAD_RETRIES = 10
UPLOAD_RETRY_S = 60

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
    if not PATH_RE.search(path): return

    normal_url = ''.join((pref, host, suff, path, frag))

    # Ensure this URL has not been used too recently in this channel.
    times = chan_times[chan.lower()]
    now = time.time()
    for time_url, time_s in times.items():
        if time_s + REPEAT_S < now: del times[time_url]
    if normal_url in times: return
    
    # Try to obtain from cache.
    mirror_url = get_cache(normal_url)
    if mirror_url:
        times[normal_url] = now
        return mirror_url

    # Otherwise, upload to a hosting website.
    if url.endswith('.webm'):
        # webmshare.com
        res = upload_webm(url)
        print(repr(res))
        mirror_url = res['video_url']
    else:
        # imgur.com
        try:
            res = imgur.upload_url(url)
        except urllib2.HTTPError as e:
            if not hasattr(e, 'read'): raise e
            print(e, file=sys.stderr)
            print(e.read(), file=sys.stderr)
            return
        except (imgur.ImgurError, urllib2.URLError):
            traceback.print_exc()
            return
        mirror_url = res.get('link')

    if mirror_url: put_cache(normal_url, mirror_url)
    times[normal_url] = now
    return mirror_url

@link('URL_COLLECT_URLS', 'URL_CMD_URLS')
def h_url_collect_urls(bot, urls, chan, id, orig_msg):
    if not chan: return
    chan = chan.lower()
    delete_indices = []

    for url_spec, index in izip(urls, count()):
        url, is_nsfw = url_collect.url_nsfw(url_spec)
        for tries in xrange(UPLOAD_RETRIES):
            if tries: yield runtime.sleep(UPLOAD_RETRY_S)
            mirror_url = get_mirror_url(url, chan)
            if mirror_url: break
        else:
            continue

        nsfw_str = '\2NSFW:\2 ' if is_nsfw else ''
        msg = '%s%s copied to <%s>.' % (nsfw_str, url, mirror_url)
        message.reply(bot, id, chan, msg, prefix=False)
        url_collect.history[chan].append([
            url_collect.nsfw_url(mirror_url, is_nsfw)])
        delete_indices.append(index)

    new_urls = [u for (i,u) in izip(count(),urls) if i not in delete_indices]
    for index in xrange(len(url_collect.history[chan])-1, -1, -1):
        if url_collect.history[chan][index] == urls:
            if new_urls:
                url_collect.history[chan][index] = new_urls
            else:
                del url_collect.history[chan][index]
            break

# Upload a WebM video file, given by URL, to webmshare.com.
# Returns a dict with keys 'video_url' and 'deletion_url'.
def upload_webm(url):
    base_domain = 'webmshare.com'
    base_url = 'https://%s/' % base_domain

    conn = httplib.HTTPSConnection(base_domain)
    headers = {'User-Agent': USER_AGENT}

    cookies = {}
    def update_cookies(resp):
        for name, value in resp.getheaders():
            if name.lower() != 'Set-Cookie'.lower(): continue
            for match in re.finditer(r'(^|(?<!;) )(?P<name>[^\s,;=]+)'
            r'=(?P<value>("([^\\"]|\\.)*"|[^\s,;]+))(;|,|$)', value):
                cookies[match.group('name')] = match.group('value')
        headers['Cookie'] = '; '.join('='.join(c) for c in cookies.iteritems())

    conn.request('GET', base_url, headers=headers)
    resp = conn.getresponse()
    assert resp.status == 200, resp.status
    update_cookies(resp)
    token = re.search(r'<input type="hidden" name="_token" '
                      r'value="(?P<v>[^"]*)">', resp.read()).group('v')
    resp.close()

    headers['Referer'] = base_url
    data, boundary = encode_multipart_form_data(OrderedDict((
        ('_token',          token),
        ('localFile',       {'value': '', 'filename': '',
                            'type': 'application/octet-stream'}),
        ('remoteFile',      url),
        ('fileExpiration',  'never'),
        ('channelSetting',  '0'),
        ('fileTitle',       ''),
        ('autoplay',        'Yes'),
        ('loop',            'Yes'),
        ('singlebutton',    ''),
    )))
    headers['Content-Type'] = 'multipart/form-data; boundary="%s"' % boundary
    conn.request('POST', base_url + 'upload', data, headers)
    resp = conn.getresponse()

    while resp.status in (301, 302, 303, 307, 308):
        update_cookies(resp)
        del headers['Content-Type']
        resp.read()
        conn.request('GET', resp.getheader('Location'), headers=headers)
        resp = conn.getresponse()

    assert resp.status == 200, resp.status
    html = resp.read()
    result = {}
    result['video_url'] = 'https:' + re.search(
                          r'src="(.*?\.webm)" type="video/webm"', html).group(1)
    result['deletion_url'] = re.search(
                           r'id="deletionUrl".*? value="(.*?)"', html).group(1)
    return result

# Encode a dict as multipart/form-data, according to RFC 7578.i Values may be
# strings, or dicts with keys 'value', optional 'filename', and optional 'type'.
# Return (encoded_data, boundary).
def encode_multipart_form_data(data):
    def encode(string):
        if isinstance(string, unicode): string = string.encode('utf8')
        return string

    parts = []
    for name, value in data.iteritems():
        part = []
        part.append('Content-Disposition: form-data; name="%s"'
                    % encode(name).replace('\\', '\\\\').replace('"', '\\"'))
        if isinstance(value, dict):
            if 'filename' in value:
                part[-1] += '; filename="%s"' % encode(value['filename'])
            if 'type' in value:
                part.append('Content-Type: %s' % value['type'])
            value = value['value']
        part.append('')
        part.extend(re.split(r'\n|\r\n?', encode(value)))
        parts.append(part)

    boundary_chars = string.letters + string.digits
    boundary, b_len = None, 10
    while boundary is None or any(
    line.startswith('--%s' % boundary) for part in parts for line in part):
        boundary = ''.join(random.choice(boundary_chars) for i in xrange(b_len))
        b_len = min(b_len + 10, 70)

    result = ('\r\n--%s\r\n' % boundary).join('\r\n'.join(p) for p in parts)
    result = ('\r\n--%s\r\n%s\r\n--%s--\r\n' % (boundary, result, boundary))
    return result, boundary
