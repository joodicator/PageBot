#==============================================================================#
import collections
import urllib2
import socket
import re
from contextlib import closing

from bs4 import BeautifulSoup

import util

#==============================================================================#
link, install, uninstall = util.LinkSet().triple()

URL_RE = re.compile('(https?://.+?)[.,;:!?>)}\]]?(?:\s|$)', re.I)
HISTORY_SIZE = 8
TIMEOUT_SECONDS = 5
READ_BYTES_MAX = 1024*1024

history = collections.defaultdict(lambda: [])

#==============================================================================#
def reload(prev):
    if hasattr(prev, 'history') and isinstance(prev.history, dict):
        history.update(prev.history)

#==============================================================================#
@link('MESSAGE')
def h_message(bot, id, target, message):
    if target is None: return
    urls = re.findall(URL_RE, message)
    if urls:
        history[target.lower()].append(urls)
        del history[target.lower()][:-HISTORY_SIZE]

#==============================================================================#
@link('HELP')
def h_help(bot, reply, args):
    reply('url [URL]',
    'Shows the titles of recently mentioned URLs, or of a specific URL.')

@link(('HELP', 'url'))
def h_help_url(bot, reply, args):
    reply('url [URL]',
    'If URL is given, shows the title (if any) of the HTML page it locates;'
    ' otherwise, show the titles of all URLs in the most recent channel'
    ' message which contains a URL, and for which "url" has not already been'
    ' called.')

@link('!url')
def h_url(bot, id, target, args, full_msg):
    from message import reply

    if args:
        urls = re.findall(URL_RE, args)
    elif target and history[target.lower()]:
        urls = history[target.lower()].pop(-1)
    else:
        return

    for url in urls:
        try:
            title = get_title(url)
            reply(bot, id, target, title, prefix=False)
        except (socket.error, urllib2.URLError, PageURLError) as e:
            reply(bot, id, target, 'Error: %s' % e, prefix=False)

#==============================================================================#
class PageURLError(Exception):
    pass

def get_title(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent',
    'Mozilla/5.0 (X11; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0')

    host = request.get_host()
    if not is_global_address(host): raise PageURLError(
        'Access to this host is denied: %s.' % host)

    title = None
    with closing(urllib2.urlopen(request, timeout=TIMEOUT_SECONDS)) as stream:
        type = stream.info().gettype()
        if 'html' in type:
            soup = BeautifulSoup(stream.read(READ_BYTES_MAX))
            title = soup.find('title').text

    title = (title and title.strip()) or '(no title)'
    return '%s [%s]' % (title, type)

#==============================================================================#
# True if the given hostname or IPV4 or IPV6 address string is not in any
# address range reserved for private or local use, or otherwise False.
def is_global_address(host):
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
        return inet6_tuple(host)[0] & 0x000f == 0x000e
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
    addr = inet6_tuple(adddr)
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
        return inet6_tuple(addr[0])

# As inet6_tuple(), but does not allow :: notation.
def inet6_tuple_base(addr):
    return tuple(int(part, 16) for part in addr.split(':')) if addr else ()

#==============================================================================#
