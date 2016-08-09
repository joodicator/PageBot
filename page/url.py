# coding=utf8

#==============================================================================#
from contextlib import closing
from itertools import *
from math import *
import collections
import traceback
import urllib
import urllib2
import socket
import ssl
import re

from bs4 import BeautifulSoup

from untwisted.magic import sign

from util import multi
import util
import runtime

from url_collect import URL_PART_RE
import url_collect

#==============================================================================#
link, install, uninstall = util.LinkSet().triple()

AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:23.0) Gecko/20100101 Firefox/23.0'
TIMEOUT_SECONDS = 20
READ_BYTES_MAX = 1024*1024
CMDS_PER_LINE_MAX = 6

MAX_AURL = 35
MAX_YT_DESC = 100

ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)

#==============================================================================#
@link('HELP*')
def h_help(bot, reply, args):
    reply('url [URL ...]',
    'Shows the titles of recently mentioned URLs, or of a specific URL.')

@link(('HELP', 'url'), ('HELP', 'title'))
def h_help_url(bot, reply, args):
    reply('url [URL ...]',
    'If URL is given, shows the title of the HTML page or image it locates;'
    ' otherwise, shows the titles of all URLs in the most recent channel'
    ' message which contains a URL, and for which "url" has not already been'
    ' called. Further "!url" commands (up to %s in total) may be given on the'
    ' same line.' % CMDS_PER_LINE_MAX)

@link('!url', '!title')
@multi('!url', '!title', limit=CMDS_PER_LINE_MAX, prefix=False)
def h_url(bot, id, target, args, full_msg, reply):
    channel = (target or ('%s!%s@%s' % id)).lower()

    if args:
        urls = url_collect.extract_urls(args)
        yield sign('URL_CMD_URLS', bot, urls, target, id, full_msg)
    elif url_collect.history[channel]:
        urls = url_collect.history[channel].pop(-1)
    else:
        urls = None

    if not urls:
        reply('No URL found.')
        return

    for url in urls:
        try:
            result = get_title_proxy(url)
            reply(result['title'])
            if target:
                yield sign('PROXY_MSG', bot, None, target, result['proxy_msg'],
                    full_msg=result['proxy_msg_full'])
            yield runtime.sleep(0.01)
        except Exception as e:
            traceback.print_exc()
            reply('Error: %s [%s]' % (e, abbrev_url(url)))

#==============================================================================#
# May be raised by get_title, get_title_proxy, etc, to indicate that the
# retrieval of information about a URL failed in some controlled fashion.
class PageURLError(Exception):
    pass

# Returns an IRC string describing the given URL, including its title; suitable
# for sending over IRC as a single line, as in response to the !url command.
def get_title(url):
    return get_title_proxy(url)['title']

# Returns a dictionary containing the following keys:
#   'title':          An IRC string describing the URL, including its title.
#   'proxy_msg':      The part of 'title' considered to be a proxy message.
#   'proxy_msg_full': The unabbreviated version of 'proxy_msg'.
def get_title_proxy(url):
    is_nsfw = False
    if type(url) is tuple:
        if url[0] == 'NSFW': is_nsfw = True
        url = url[1]

    url = utf8_url_to_ascii(url)

    request = urllib2.Request(url)
    request.add_header('User-Agent', AGENT)

    host = request.get_host()
    if not is_global_address(host): raise PageURLError(
        'Access to this host is denied: %s.' % host)

    with closing(urllib2.urlopen(
    request, timeout=TIMEOUT_SECONDS, context=ssl_context)) as stream:
        info = stream.info()
        ctype = info.gettype()
        size = info['Content-Length'] if 'Content-Length' in info else None
        final_url = stream.geturl()
        parts = get_title_parts(final_url, ctype, stream=stream)

    title = parts.get('title', 'Title: (none)')
    extra = parts.get('info', ctype)
    extra_full = parts.get('info_full', extra)
    final_url = parts.get('url', final_url)
    size = parts.get('size', size)

    url_info = []
    if final_url != url:
        url_info[:0] = ['%s -> %s' % (abbrev_url(url),
            abbrev_url_middle(final_url))]
    else:
        url_info[:0] = [abbrev_url(url)]
    if size:
        url_info[:0] = [bytes_to_human_size(size)]
    if extra: url_info[:0] = [extra]
    
    url_info = '; '.join(url_info)
    if is_nsfw: url_info = '%s \2NSFW\2' % url_info

    return {
        'title':          '%s [%s]' % (title, url_info),
        'proxy_msg':      extra,
        'proxy_msg_full': extra_full }

#-------------------------------------------------------------------------------
# Given a URL and its MIME type (according to HTTP), and possibly also given a
# file object containing a stream with the contents of the URL, returns a
# dictionary containing some or all of the following keys:
#   'title':     the main title of the URL.
#   'info':      a string with supplementary information about the URL.
#   'info_full': if 'info' has been abbreviated, the unabbreviated version.
#   'url':       the (new) URL to which the original URL ultimately directs.
#   'size':      the size in bytes of the resource given by the 'url' key.
def get_title_parts(url, type, stream=None):
    match = URL_PART_RE.match(url)
    path, query = decode_url_path(match.group('path'))
    # YouTube
    if re.search(r'(^|\.)youtube\.com$', match.group('host')):
        res = get_title_youtube(url, type)
        if res: return res
    # imgur
    if re.search(r'(^|\.)imgur\.com$', match.group('host')):
        res = get_title_imgur(url, type, stream)
        if res: return res
    # HTML
    if 'html' in type:
        res = get_title_html(url, type, stream=stream)
        if res: return res
    # image files
    if type.startswith('image/'):
        return get_title_image(url, type)
    # Other
    return dict()

#-------------------------------------------------------------------------------
def get_title_html(url, type, stream=None):
    if stream is None:
        request = urllib2.Request(url)
        request.add_header('User-Agent', AGENT)
        stream = urllib2.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=ssl_context)
    
    with closing(stream):
        soup = BeautifulSoup(
            stream.read(READ_BYTES_MAX),
            from_encoding = stream.info().getparam('charset'))

    title = soup.find('title')
    if title:
        title = 'Title: %s' % format_title(title.text.strip())
        return { 'title': title }

#-------------------------------------------------------------------------------
def get_title_image(url, type):
    title = google_image_best_guess(url)
    title = 'Best guess: %s' % (format_title(title) if title else '(none)')
    return { 'title': title }

#-------------------------------------------------------------------------------
def get_title_youtube(url, type):
    match = URL_PART_RE.match(url)
    path, query = decode_url_path(match.group('path'))
    if path != '/watch' or not query.get('v'): return
    video_id = query['v']
    try:
        from youtube import youtube
        result = youtube.videos().list(id=video_id,
            part='snippet,statistics,contentDetails').execute()['items'][0]

        title = result['snippet']['title']
        desc = result['snippet']['description']
        channel = result['snippet']['channelTitle']
        #views = result['statistics']['viewCount']
        #likes = result['statistics']['likeCount']
        #dislikes = result['statistics']['dislikeCount']
        duration = result['contentDetails']['duration']

        desc_full = desc
        desc = re.sub(r'\r\n|\r|\n', ' ', desc)
        desc = '%s' % desc[:MAX_YT_DESC]
        full_urls = url_collect.extract_urls(desc_full)
        for desc_url in url_collect.extract_urls(desc):
            if (desc_url not in full_urls and desc.endswith(desc_url)
            and not ABBREV_URL_RE.match(desc_url).group('path')):
                desc = desc[:-len(desc_url)]
                break
        desc = desc + '...' if len(desc) < len(desc_full) else desc
        
        duration = iso8601_period_human(duration)

        return {
            'title':
                'Title: %s' % format_title(title),
            'info':
                'Duration: %s; Channel: %s; Description: "%s"'
                % (duration, channel, desc),
            'info_full':
                'Duration: %s; Channel: %s; Description: "%s"'
                % (duration, channel, desc_full) }
    except Exception as e:
        traceback.print_exc(e)

#-------------------------------------------------------------------------------
def get_title_imgur(url, type, stream=None):
    match = URL_PART_RE.match(url)
    if match.group('host') not in ('imgur.com', 'i.imgur.com'): return
    path, query = decode_url_path(match.group('path'))
    path_match = re.match(
        r'(/gallery|/r/[^/]+)?/(?P<id>[a-zA-Z0-9]+)(\.[a-zA-Z]+)?$', path)

    try:
        import imgur
        info = imgur.image_info(path_match.group('id'))
        img_url, img_type = info['link'], info['type']
    except:
        traceback.print_exc()
        info = None
        img_url, img_type = url, type

    if img_url.endswith('.gifv'):
        img_url = re.sub(r'\.gifv$', '.gif', img_url)
        img_type = 'image/gif'
    
    title = get_title_image(img_url, img_type)['title']
    if info and info.get('title') and not URL_PART_RE.match(info['title']):
        title = 'Title: %s -- %s' % (format_title(info['title']), title)
    elif 'html' in type:
        html_title = get_title_html(url, type, stream)['title']
        if (html_title and not URL_PART_RE.match(html_title)
        and html_title != 'Title: \2Imgur: The most awesome images on the Internet\2'
        and html_title != 'Title: \2Imgur\2'):
            html_title = re.sub(r'^\002(.*) - Imgur\002$', r'\1', html_title)
            title = '%s -- %s' % (html_title, title)

    if info and info.get('size'):
        size = info['size']
    else:
        size = None

    if info and info.get('gifv') and not path.endswith('.gif'):
        img_url = info['gifv']
        img_type = None
        size = None

    if decode_url_path(URL_PART_RE.match(img_url).group('path'))[0] == path:
        img_url = url

    return {'title':title, 'info':img_type, 'url':img_url, 'size':size}

#-------------------------------------------------------------------------------
ABBREV_URL_RE = re.compile(
    r'(?P<site>.+?://[^/]*)'
    r'(?P<path>/?.*)')

def abbrev_url(url):
    url = url_to_unicode(url)
    if len(url) > MAX_AURL:
        url = ABBREV_URL_RE.match(url).group('path')
        return '...' + url[-(MAX_AURL-3):]
    else:
        return url

def abbrev_url_middle(url):
    url = url_to_unicode(url)
    site, path = ABBREV_URL_RE.match(url).group('site', 'path')
    return site + '/...' + \
           path[1:][min(-MAX_AURL/2, len(path)-1-(MAX_AURL-3)):] \
           if len(url) > MAX_AURL else url

def url_to_unicode(url):
    if type(url) == unicode: url = url.encode('utf8')
    url = ascii_url_to_utf8(url)
    try: return url.decode('utf8')
    except UnicodeError: return url

def format_title(title):
    title = '\2%s\2' % re.sub(r'\r\n|\r|\n', ' ', title)
    return title

def bytes_to_human_size(bytes):
    bytes = int(bytes)
    for (m,s) in (1,'B'),(2**10,'KiB'),(2**20,'MiB'),(2**30,'GiB'):
        units = bytes / m
        if units >= 1024: continue
        return '%.1f %s' % (units, s)

#===============================================================================
# Returns the "best guess" phrase that Google's reverse image search offers to
# describe the image at the given URL, or None if no such phrase is offered.
def google_image_best_guess(url):
    PHRASE = 'Best guess for this image:'
    soup = google_image_title_soup(url)
    node = soup.find(text=re.compile(re.escape(PHRASE)))
    return node and node.parent.text.replace(PHRASE, '').strip()

def google_image_title_soup(url):
    request = urllib2.Request('https://www.google.com/searchbyimage?'
        + urllib.urlencode({'image_url':url, 'safe':'off'}))
    request.add_header('Referer', 'https://www.google.com/imghp?hl=en&tab=wi')
    request.add_header('User-Agent', AGENT)
    with closing(urllib2.urlopen(request,
    timeout=TIMEOUT_SECONDS, context=ssl_context)) as stream:
        text = stream.read(READ_BYTES_MAX)
        with open('/tmp/url', 'w') as file:
            file.write(text)
        return BeautifulSoup(text)

#==============================================================================#
# True if the given hostname or IPV4 or IPV6 address string is not in any
# address range reserved for private or local use, or otherwise False.
def is_global_address(host):
    # See: http://en.wikipedia.org/wiki/Reserved_IP_addresses
    family, _, _, _, address = socket.getaddrinfo(host, None)[0]
    if family == socket.AF_INET:
        host, _ = address
        addr = inet4_int(host)
        for range in ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
        '169.254.0.0/16', '172.16.0.0/12', '192.0.0.0/24', '192.0.2.0/24',
        '192.88.99.0/24', '192.168.0.0/16', '198.18.0.0/15', '198.51.100.0/24',
        '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4', '255.255.255.255/32'):
            prefix, size = range.split('/')
            prefix, size = inet4_int(prefix), int(size)
            if addr>>(32-size) == prefix>>(32-size): return False
        return True
    elif family == socket.AF_INET6:
        host, _, _, _ = address
        addr = inet6_int(host)
        for range in ('::/128', '::1/128', '::ffff:0:0/96', '64:ff9b::/96',
        '2001::/32', '2001:10::/28', '2001:db8::/32', '2002::/16', 'fc00::/7',
        'fe80::/10', 'ff00::/8'):
            prefix, size = range.split('/')
            prefix, size = inet6_int(prefix), int(size)
            if addr>>(128-size) == prefix>>(128-size): return False
        return True
    else:
        raise PageURLError(
            'Unsupported address family for "%s": %s.' % (host, family))    

#==============================================================================#
# IPV4 address string to integer.
def inet4_int(addr):
    addr = inet4_tuple(addr)
    return sum(addr[-i-1]<<(8*i) for i in xrange(4))

# IPV6 address string to integer.
def inet6_int(addr):
    addr = inet6_tuple(addr)
    return sum(addr[-i-1]<<(16*i) for i in xrange(8))

# IPV4 address string to 4-tuple of integers.
def inet4_tuple(addr):
    return tuple(int(part) for part in addr.split('.'))

# IPV6 address string to 8-tuple of integers, allowing :: notation.
def inet6_tuple(addr):
    addr = addr.split('::', 1)
    if len(addr) > 1:
        addr0, addr1 = inet6_tuple_base(addr[0]), inet6_tuple_base(addr[1])
        return addr0 + (0,)*(8 - len(addr0) - len(addr1)) + addr1
    else:
        return inet6_tuple_base(addr[0])

# As inet6_tuple(), but does not allow :: notation.
def inet6_tuple_base(addr):
    return tuple(int(part, 16) for part in addr.split(':')) if addr else ()

#==============================================================================#
def utf8_url_to_ascii(url):
    m = URL_PART_RE.match(url)
    if not m: return url
    return m.group('pref') \
         + utf8_host_to_ascii(m.group('host')) \
         + m.group('suff') \
         + utf8_path_to_ascii(m.group('path')) \
         + m.group('frag')

def utf8_host_to_ascii(host):
    parts = host.split('.')
    for i in xrange(len(parts)):
        try: parts[i] = parts[i].decode('utf8')
        except UnicodeError: continue
        if parts[i].encode('ascii', 'ignore') == parts[i]: continue
        parts[i] = 'xn--' + parts[i].lower().encode('punycode')
    return '.'.join(parts)

def utf8_path_to_ascii(path):
    return path

#-------------------------------------------------------------------------------
def ascii_url_to_utf8(url):
    m = URL_PART_RE.match(url)
    if not m: return url
    return m.group('pref') \
         + ascii_host_to_utf8(m.group('host')) \
         + m.group('suff') \
         + ascii_path_to_utf8(m.group('path')) \
         + m.group('frag')

def ascii_host_to_utf8(host):
    parts = host.split('.')
    for i in xrange(len(parts)):
        if not parts[i].startswith('xn--'): continue
        try: parts[i] = parts[i][4:].decode('punycode').encode('utf8')
        except UnicodeError: pass
    return '.'.join(parts)

def ascii_path_to_utf8(path):
    return path

#-------------------------------------------------------------------------------
# Returns (p, q), where p is the given URL path excluding any query part, and
# q is a (possibly empty) dict mapping query names to (possibly null) values.
def decode_url_path(url_path):
    match = re.match(r'(?P<p>[^?]*)(\?(?P<q>.*))?', url_path)
    data = dict()
    if match.group('q'):
        for item in re.split(r'&|;', match.group('q')):
            item = item.split('=', 1)
            key = urllib.unquote_plus(item[0])
            val = urllib.unquote_plus(item[1]) if len(item) > 1 else None
            data[key] = val
    return (match.group('p'), data)

#-------------------------------------------------------------------------------
# Converts an ISO-8601 time period to a human-readable format.
def iso8601_period_human(spec):
    sec, hou, min, day, mon, yea = 0, 0, 0, 0, 0, 0
    match = re.match(r'P(?P<d>.*?)(T(?P<t>.*))?$', spec)
    if not match: raise Exception('Invalid ISO-8601 time period: %s.' % spec)
    for m in re.finditer(r'(?P<n>\d+)(?P<t>\D)', match.group('d')):
        type, n = m.group('t'), int(m.group('n'))
        if   type == 'Y': yea += n
        elif type == 'M': mon += n
        elif type == 'W': day += n*7
        elif type == 'D': day += n
        else: raise Exception('Unknown ISO-8601 date unit: %s.' % type)
    for m in re.finditer(r'(?P<n>\d+)(?P<t>\D)', match.group('t') or ''):
        type, n = m.group('t'), int(m.group('n'))
        if   type == 'H': hou += n
        elif type == 'M': min += n
        elif type == 'S': sec += n
        else: raise Exception('Unknown ISO-8601 time unit: %s.' % type)
    return ''.join((
        '%d year%s, '  % (yea, 's' if yea>1 else '') if yea else '',
        '%d month%s, ' % (mon, 's' if mon>1 else '') if mon else '',
        '%d day%s, '   % (day, 's' if day>1 else '') if day else '',
        '%02d:' % hou if hou else '', '%02d:%02d' % (min, sec)))
