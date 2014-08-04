#==============================================================================#
import collections
import re

from untwisted.magic import sign
import util

#==============================================================================#
link, install, uninstall = util.LinkSet().triple()

URL_RE = re.compile(r'(https?://.+?)[.,;:!?>)}\]]?(?:\s|[\x01-\x1f]|$)', re.I)
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
@link('MESSAGE', 'UNOTICE', 'OTHER_PART', 'OTHER_QUIT')
def h_message(bot, id, target, message, *args):
    if not message: return
    yield sign('URL_COLLECT_MSG', bot, message, target, id)

@link('OTHER_KICKED')
def h_other_kicked(bot, other_nick, op_id, channel, message):
    if not message: return
    yield sign('URL_COLLECT_MSG', bot, message, channel)

@link('TELL_DELIVERY')
def h_tell_delivery(bot, from_id, to_id, channel, message):
    yield sign('URL_COLLECT_MSG', bot, message, channel)

@link('COMMAND')
def h_command(bot, id, target, cmd, args, full_msg):
    if cmd in ('!url', '!title'): return
    yield sign('URL_COLLECT_MSG', bot, args, target, id)

@link('URL_COLLECT_MSG')
def examine_message(bot, message, channel, id=None):
    source = (channel or ('%s!%s@%s' % id)).lower()
    urls = extract_urls(message)
    if not urls: return

    history[source].append(urls)
    del history[source][:-HISTORY_SIZE]

    yield sign('URL_COLLECT_URLS', bot, urls, channel, id, message)

def extract_urls(message):
    urls = re.findall(URL_RE, message)
    if re.search(r'NSFW', message, re.I):
        urls = map(lambda u: ('NSFW',u), urls)
    return urls    
