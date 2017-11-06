#==============================================================================#
from itertools import *
import collections
import re

from untwisted.magic import sign
import util

#==============================================================================#
link, install, uninstall = util.LinkSet().triple()

URL_RE = re.compile(
    r'<(?P<a>https?://[^>]+)>'
    r'|(?P<b1>https?://.+?)(?P<b2>[.,;:!?"\'>)}\]]*)(?:\s|[\x01-\x1f]|$)', re.I)
HISTORY_SIZE = 12 # To preserve channel privacy, do not make this too large.

URL_PART_RE = re.compile(
    r'(?P<pref>.+?://(.+?@)?)'
    r'(?P<host>.+?)'
    r'(?P<suff>(:.+?)?)'
    r'(?P<path>(/.*?)?)'
    r'(?P<frag>(#.*)?)$')

history = collections.defaultdict(lambda: [])

#==============================================================================#
def reload(prev):
    if hasattr(prev, 'history') and isinstance(prev.history, dict):
        history.update(prev.history)

#==============================================================================#
@link('MESSAGE', 'UNOTICE')
def h_message(bot, id, target, message, *args):
    if not message: return
    yield examine_message(bot, id, target or id.nick, message)

@link('PROXY_MSG')
def h_proxy_msg(bot, id, target, msg, full_msg=None, no_url=False, **kwds):
    if no_url: return
    yield examine_message(bot, id, target, msg, full_msg=full_msg)

@link('COMMAND')
def h_command(bot, id, target, cmd, args, full_msg):
    if cmd in ('!url', '!title'): return
    yield examine_message(bot, id, target or id.nick, args)

@util.msub(link, 'url_collect.examine_message')
def examine_message(bot, id, source, message, full_msg=None):
    if isinstance(source, tuple): source = '%s!%s@%s' % source
    source = source.lower()
    urls = extract_urls(message, full_msg=full_msg)
    if not urls: return

    history[source].append(urls)
    del history[source][:-HISTORY_SIZE]

    yield sign('URL_COLLECT_URLS', bot, urls, source, id, message)

def extract_urls(message, full_msg=None):
    urls = []
    start = 0
    between = ''
    for match in re.finditer(URL_RE, message):
        between += message[start:match.start()]
        if match.group('a'):
            urls.append(match.group('a'))
        else:
            b1, b2 = match.group('b1'), match.group('b2')
            op, cl = '<({[', '>)}]'
            b2 = ''.join(takewhile(lambda c: c in cl and (
                op[cl.index(c)] in b1 or op[cl.index(c)] not in between), b2))
            urls.append(b1 + b2)
        start = match.end()
    if full_msg is not None:
        full_urls = extract_urls(full_msg)
        urls = filter(lambda u: u in full_urls, urls)
    if re.search(r'\bNSFW\b', message, re.I):
        urls = map(lambda u: ('NSFW', u), urls)
    return urls    

#==============================================================================#
# ('NSFW',url) -> (url,True); url -> (url,False)
def url_nsfw(spec):
    return (spec[1],True) \
        if type(spec) is tuple and spec[0] == 'NSFW' \
      else (spec, False)

# (url,True) -> ('NSFW',url); (url,False) -> url
def nsfw_url(url, is_nsfw):
    return ('NSFW',url) if is_nsfw else url
