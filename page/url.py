# coding=utf8

#==============================================================================#
# Possible Extensions:
# - Recognise images tagged by the poster as NSFW.
# - Show YouTube video descriptions, etc, for YT videos.
# - Interpret imgur HTML URLs (etc) as images.

#==============================================================================#
from contextlib import closing
from itertools import *
from math import *
import collections
import traceback
import urllib
import urllib2
import socket
import re

from bs4 import BeautifulSoup
from untwisted.magic import sign

from util import multi
import util
import runtime

#==============================================================================#
link, install, uninstall = util.LinkSet().triple()

URL_RE = re.compile(r'(https?://.+?)[.,;:!?>)}\]]?(?:\s|[\x01-\x1f]|$)', re.I)
AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:23.0) Gecko/20100101 Firefox/23.0'
HISTORY_SIZE = 8
TIMEOUT_SECONDS = 20
READ_BYTES_MAX = 1024*1024
CMDS_PER_LINE_MAX = 4

history = collections.defaultdict(lambda: [])

#==============================================================================#
def reload(prev):
    if hasattr(prev, 'history') and isinstance(prev.history, dict):
        history.update(prev.history)

#==============================================================================#
@link('MESSAGE', 'UNOTICE', 'OTHER_PART', 'OTHER_QUIT')
def h_message(bot, id, target, message):
    examine_message(message, target, id)

@link('OTHER_KICKED')
def h_other_kicked(bot, other_nick, op_id, channel, message):
    examine_message(message, channel)

@link('TELL_DELIVERY')
def h_tell_delivery(bot, from_id, to_id, channel, message):
    examine_message(message, channel)

@link('COMMAND')
def h_command(bot, id, target, cmd, args, full_msg):
    if cmd in ('!url', '!title'): return
    examine_message(args, target, id)

def examine_message(message, channel, id):
    channel = channel or ('%s!%s@%s' % id).lower()
    urls = re.findall(URL_RE, message)
    if urls:
        history[channel].append(urls)
        del history[channel][:-HISTORY_SIZE]

#==============================================================================#
@link('HELP*')
def h_help(bot, reply, args):
    reply('url [URL ...]',
    'Shows the titles of recently mentioned URLs, or of a specific URL.')

@link(('HELP', 'url'))
@link(('HELP', 'title'))
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
    channel = target or ('%s!%s@%s' % id).lower()

    if args:
        urls = re.findall(URL_RE, args)
    elif history[channel]:
        urls = history[channel].pop(-1)
    else:
        urls = None

    if not urls:
        reply('No URL found.')
        return

    for url in urls:
        try:
            reply(get_title(url))
            yield runtime.sleep(0.01)
        except (socket.error, urllib2.URLError, PageURLError) as e:
            reply('Error: %s [%s]' % (e, abbrev_url(url)))    

#==============================================================================#
class PageURLError(Exception):
    pass

def get_title(url):
    url = utf8_url_to_ascii(url)

    request = urllib2.Request(url)
    request.add_header('User-Agent', AGENT)

    host = request.get_host()
    if not is_global_address(host): raise PageURLError(
        'Access to this host is denied: %s.' % host)

    with closing(urllib2.urlopen(request, timeout=TIMEOUT_SECONDS)) as stream:
        info = stream.info()
        type = info.gettype()
        size = info['Content-Length'] if 'Content-Length' in info else None
        final_url = stream.geturl()

    title = None
    if 'html' in type:
        title = get_title_html(url)
    elif type.startswith('image/'):
        title = get_title_image(url)

    title = title or '(no title)'
    url_info = []
    if final_url == url:
        url_info[:0] = [abbrev_url(url)]
    else:
        url_info[:0] = ['%s -> %s' % (abbrev_url(url), abbrev_url_middle(final_url))]
    if size:
        url_info[:0] = [bytes_to_human_size(size)]
    url_info[:0] = [type]
    return '%s [%s]' % (title, '; '.join(url_info))

def abbrev_url(url):
    url = url_to_unicode(url)
    return '...' + url[-31:] if len(url) > 34 else url

def abbrev_url_middle(url):
    url = url_to_unicode(url)
    return url[:15] + '...' + url[-15:] if len(url) > 34 else url

def url_to_unicode(url):
    if type(url) == unicode: url = url.encode('utf8')
    url = ascii_url_to_utf8(url)
    try: return url.decode('utf8')
    except UnicodeError: return url

def get_title_html(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent', AGENT)
    with closing(urllib2.urlopen(request, timeout=TIMEOUT_SECONDS)) as stream:
        soup = BeautifulSoup(stream.read(READ_BYTES_MAX))
    title = soup.find('title')
    return title and format_title(title.text.strip())

def get_title_image(url):
    title = google_image_best_guess(url)
    return 'Best guess: %s' % (format_title(title) if title else '(none)')

def format_title(title):
    title = '\2%s\2' % title

    try:
        import kakasi_lib
        main_title = re.match('\2(.*?)( - YouTube)?\2$', title).group(1)
        if kakasi_lib.is_ja(main_title):
            title = '%s (read: \2%s\2)' % (title, kakasi_lib.kakasi(main_title))
    except:
        traceback.print_exc()

    return title

def bytes_to_human_size(bytes):
    bytes = int(bytes)
    for (m,s) in (1,'B'),(2**10,'KiB'),(2**20,'MiB'),(2**30,'GiB'):
        units = bytes / m
        if units >= 1024: continue
        return '%.1f %s' % (units, s)

#==============================================================================#
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
    with closing(urllib2.urlopen(request, timeout=TIMEOUT_SECONDS)) as stream:
        return BeautifulSoup(stream.read(READ_BYTES_MAX))    

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
URL_PART_RE = re.compile(
    r'(?P<pref>.+?://(.+?@)?)'
    r'(?P<host>.+?)'
    r'(?P<suff>(:.+?)?)'
    r'(?P<path>(/.*?)?)'
    r'(?P<frag>(#.*)?)$')

#-------------------------------------------------------------------------------
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

#===============================================================================
