from __future__ import print_function

import traceback
import datetime
import time
import json
import re

from untwisted.magic import sign, hold

import nickserv
import runtime
import channel
import util

RPL_WHOISUSER = '311'

CREDENTIALS_FILE = 'conf/identity.py'
PREV_HOSTS_FILE  = 'state/identity_hosts.json'

link, install, uninstall = util.LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'nickserv')

prev_track_id = None
def reload(prev):
    global prev_track_id
    if hasattr(prev, 'track_id') and type(prev.track_id) is dict:
        prev_track_id = prev.track_id

@link('POST_RELOAD')
def h_post_reload(bot):
    global prev_track_id
    all_nicks = set()
    for chan, nicks in channel.track_channels.iteritems():
        all_nicks.update(nick.lower() for nick in nicks)
    if prev_track_id is not None:
        for nick in all_nicks:
            track_id[nick] = Record()
            if nick in prev_track_id and hasattr(prev_track_id[nick], 'hostmask'):
                track_id[nick].hostmask = prev_track_id[nick].hostmask
        prev_track_id = None
    yield refresh(bot, list(all_nicks))

#-------------------------------------------------------------------------------
# track_id[nick.lower()]
# is a Record instance, which exists only if the bot shares a channel with nick
# or if nick is the bot's own nick.
class Record(object):
    __slots__ = 'hostmask', 'access'
    def __init__(self, hostmask=None):
        self.hostmask = hostmask # 'nick!user@host' if known, else None.
        self.access = set()      # set of access_name.lower() granted.
    def __repr__(self):
        return 'Record(%s)' % ', '.join(
            '%s=%r' % (attr, getattr(self,attr))
            for attr in Record.__slots__)

track_id = dict()

#-------------------------------------------------------------------------------
# credentials[name.lower()] - list of credentials providing access to name.
def add_credentials(name, *creds):
    old_creds = credentials.get(name.lower(), [])
    new_creds = old_creds + [c for c in creds if c not in old_creds]
    credentials[name.lower()] = new_creds

def read_credentials():
    try:
        raw_creds = util.fdict(CREDENTIALS_FILE)
    except Exception:
        traceback.print_exc()
        return dict()
    return { name.lower():creds for (name,creds) in raw_creds.iteritems() }

credentials = read_credentials()

#-------------------------------------------------------------------------------
# prev_hosts[access_name.lower()]
# is a list of (unique) 'nick!user@host' which have had access to access_name,
# in chronological order with the most recent last.
def read_prev_hosts():
    new_prev_hosts = dict()
    try:
        with open(PREV_HOSTS_FILE) as file:
            new_prev_hosts = util.recursive_encode(json.load(file), 'utf8')
    except ValueError: traceback.print_exc()
    except IOError:    traceback.print_exc()
    return new_prev_hosts

def write_prev_hosts(new_prev_hosts):
    try:
        with open(PREV_HOSTS_FILE, 'w') as file:
            json.dump(new_prev_hosts, file, indent=4)
    except ValueError: traceback.print_exc()
    except IOError:    traceback.print_exc()

prev_hosts = read_prev_hosts()

#===============================================================================
# yield check_access(bot, query, name) -> True iff query has access to name.
# where query = nick or ID(nick, user, host)
@util.mfun(link, 'identity.check_access')
def check_access(bot, query, name, ret):
    name = name.lower()

    if isinstance(query, tuple):
        nick = query.nick.lower()
        host = ('%s!%s@%s' % query).lower()
        id = query
    else:
        nick = query.lower()
        host = yield get_hostmask(bot, nick)
        if host:
            match = re.match(r'(.*)!(.*)@(.*)$', host)
            id = util.ID(*match.groups())
        else:
            id = None

    # If a positive result is already cached, return that result.
    if nick in track_id and name in track_id[nick].access:
        yield ret(True)
        return

    creds = credentials.get(name, list())
    creds = sorted(creds, key=lambda cred:
        0 if cred[0] == 'hostmask' else
        1 if cred[0] == 'access' else
        2 if cred[0] == 'prev_hosts' else
        3 if cred[0] == 'nickserv' else
        4)

    has_access = False
    for cred in creds:
        if cred[0] == 'hostmask' and len(cred) > 1:
            # Authenticate using a hostmask with wildcards.
            pattern = util.wc_to_re(cred[1])
            if host and re.match(pattern, host, re.I):
                has_access = True
                break
        elif cred[0] == 'nickserv' and len(cred) > 1:
            # Authenticate using NickServ STATUS.
            cred_nick = cred[1].lower()
            if cred_nick != nick:
                continue
            status = yield nickserv.status(bot, nick)
            if status > 1:
                has_access = True
                break
        elif cred[0] == 'prev_hosts' and len(cred) > 1:
            # Authenticate using previously authenticated hosts.
            if not id or name.lower() not in prev_hosts:
                continue
            userhost = '%s@%s' % (id.user, id.host)
            if userhost in prev_hosts[name][-cred[1]:]:
                has_access = True
                break
        elif cred[0] == 'access' and len(cred) > 1:
            # Authenticate based on a different access name.
            has_access = yield check_access(bot, id or nick, cred[1])
            if has_access:
                break

    if has_access:
        yield grant_access(bot, id or nick, name)

    yield ret(has_access)

#-------------------------------------------------------------------------------
# yield get_hostmask(bot, nick) -> 'nick!user@host' or None
@util.mfun(link, 'identity.get_hostmask')
def get_hostmask(bot, nick, ret):
    nick = nick.lower()
    if nick in track_id and track_id[nick].hostmask:
        yield ret(track_id[nick].hostmask)
        return
    result = yield who(bot, nick)
    if not result:
        yield ret(None)
        return
    r_nick, r_user, r_host, r_real = result
    hostmask = '%s!%s@%s' % (r_nick, r_user, r_host)
    if nick in track_id:
        track_id[nick].hostmask = hostmask
    elif nick.lower() == bot.nick.lower():
        track_id[nick] = Record(hostmask=hostmask)
    yield ret(hostmask)

#-------------------------------------------------------------------------------
# yield get_id(bot, nick) -> ID(nick,user,host) or None
@util.mfun(link, 'identity.get_id')
def get_id(bot, nick, ret):
    hostmask = yield get_hostmask(bot, nick)
    if hostmask:
        yield ret(hostmask_to_id(hostmask))
    else:
        yield ret(None)

def hostmask_to_id(hostmask):
    return util.ID(*re.match(r'(.*)!(.*)@(.*)$', hostmask).groups())

#-------------------------------------------------------------------------------
# yield refresh(bot, nicks) -> re-check certain credentials for each nick.
@util.msub(link, 'identity.refresh')
def refresh(bot, nicks):
    nicks = map(str.lower, nicks)
    cred_nicks = dict()
    for access_name, creds in credentials.iteritems():
        for cred in creds:
            if cred[0] == 'nickserv' and len(cred) > 1:
                cred_nick = cred[1].lower()
                if cred_nick not in nicks: continue
                access_names = cred_nicks.get(cred_nick, [])
                if access_name.lower() in access_names: continue
                cred_nicks[cred_nick] = access_names + [access_name.lower()]

    status = yield nickserv.statuses(bot, cred_nicks.keys())
    for nick, access_names in cred_nicks.iteritems():
        if status.get(nick) < 2: continue
        for access_name in access_names:
            yield grant_access(bot, nick, access_name)

#-------------------------------------------------------------------------------
# yield grant_access(bot, nick, access_name)
@util.msub(link, 'identity.grant_access')
def grant_access(bot, nick_or_id, access_name):
    if isinstance(nick_or_id, tuple):
        nick, id = nick_or_id.nick, None
    else:
        nick, id = nick_or_id, None

    # Update any existing identity-tracking record.
    if nick.lower() in track_id:
        if access_name.lower() in track_id[nick.lower()].access:
            return
        track_id[nick.lower()].access.add(access_name.lower())

    # Record information for the purposes of the 'prev_hosts' credential.
    max_prev_hosts = 0
    for cred in credentials.get(access_name.lower(), list()):
        if cred[0] != 'prev_hosts' or len(cred) < 2: continue
        max_prev_hosts = max(cred[1], max_prev_hosts)
    if max_prev_hosts:
        if not id:
            hostmask = yield get_hostmask(bot, nick)
            if hostmask:
                id = util.ID(*re.match(r'(.*)!(.*)@(.*)', hostmask).groups())
        if id:
            userhost = '%s@%s' % (id.user, id.host)
            hosts = prev_hosts.get(access_name.lower(), list())
            if userhost.lower() not in map(str.lower, hosts):
                hosts = (hosts + [userhost])[-max_prev_hosts:]
            prev_hosts[access_name.lower()] = hosts
            write_prev_hosts(prev_hosts)

    # Grant any 'access' credentials that are satisfied as a result.
    for further_name, creds in credentials.iteritems():
        for cred in creds:
            if cred[0] != 'access' or len(cred) < 2: continue
            if cred[1].lower() != access_name.lower(): continue
            yield grant_access(bot, nick or id, further_name)
    
    yield sign('GAIN_ACCESS', bot, nick, access_name)

#===============================================================================
# yield who(bot, query_nick) -> (nick, user, host, real) or None
whois_cache = dict()
@util.mfun(link, 'identity.who')
def who(bot, nick, ret):
    for cnick, (_, ctime) in whois_cache.items():
        if ctime < time.time() - 10:
            del whois_cache[cnick]

    cached = whois_cache.get(nick.lower())
    if cached is not None and cached[0] is not None:
        result = cached[0]
    else:
        if cached is None:
            bot.send_cmd('WHOIS %s' % nick)
            whois_cache[nick.lower()] = (None, time.time())
        timeout = yield runtime.timeout(5)
        result = None
        while True:
            event, args = yield hold(bot, RPL_WHOISUSER, timeout)
            if event != RPL_WHOISUSER: break
            (e_bot, e_source, e_target,
             e_nick, e_user, e_host, e_star, e_real) = args
            if e_nick.lower() != nick.lower(): continue
            result = (e_nick, e_user, e_host, e_real)
            whois_cache[nick.lower()] = (result, time.time())
    
    yield ret(result)

#===============================================================================
@link('NAMES_SYNC')
def h_names_sync(bot, chan, chan_nicks, chan_umodes):
    # Upon receiving the nick list for a channel, create identity-tracking
    # records for any previously unknown nicks in the channel.
    refresh_nicks = []
    for nick in chan_nicks:
        if nick.lower() == bot.nick.lower(): continue
        if nick.lower() not in track_id:
            track_id[nick.lower()] = Record()
        refresh_nicks.append(nick)
    if not refresh_nicks: return
    yield refresh(bot, refresh_nicks)

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    # Create an identity-tracking record.
    nick = id.nick.lower()
    if nick not in track_id:
        track_id[nick] = Record()
    track_id[nick].hostmask = '%s!%s@%s' % id
    yield refresh(bot, [nick])

@link('SELF_NICK',  a=lambda bot,     new_nick: (None, bot.nick, new_nick))
@link('OTHER_NICK', a=lambda bot, id, new_nick: (id,   id.nick,  new_nick))
def h_other_nick(bot, *args, **kwds):
    # Rename any identity-tracking record.
    id, old_nick, new_nick = kwds.pop('a')(bot, *args, **kwds)
    if old_nick.lower() in track_id:
        record = track_id.pop(old_nick.lower())
        if id is None and record.hostmask:
            id = hostmask_to_id(record.hostmask)
        if id is not None:
            record.hostmask = '%s!%s@%s' % (new_nick, id.user, id.host)
        track_id[new_nick.lower()] = record

@link('CHAN_MODE')
def h_chan_mode(bot, source, chan, modes):
    # Upon a channel-user-mode change, check for any access changes.
    pre_ms, pre_cs = bot.isupport['PREFIX']
    for (pm, mode, arg) in modes:
        if mode in pre_ms and arg:
            yield refresh(bot, [arg])

@link('OTHER_PART',     a=lambda id, chan, *args:           (id.nick, chan))
@link('OTHER_KICKED',   a=lambda nick, op_id, chan, *args:  (nick, chan))
def h_other_exit(bot, *args, **kwds):
    # If no more common channels exist, delete any identity-tracking record.
    exit_nick, exit_chan = map(str.lower, kwds['a'](*args))
    for chan, nicks in channel.track_channels.iteritems():
        if chan == exit_chan:
            continue
        if any(exit_nick == nick.lower() for nick in nicks):
            break
    else:
        if exit_nick.lower() in track_id:
            del track_id[exit_nick.lower()]

@link('OTHER_QUIT')
def h_other_quit(bot, id, msg):
    # Delete any identity-tracking record.
    if id.nick.lower() in track_id:
        del track_id[id.nick.lower()]

@link('SELF_PART')
@link('SELF_KICKED')
def h_self_exit(bot, chan, *args):
    # Delete identity-tracking records for nicks for which
    # there is no longer a common channel.
    chan = chan.lower()
    exit_nicks = set(n.lower() for n in channel.track_channels[chan])
    for ochan, onicks in channel.track_channels.iteritems():
        if ochan == chan: continue
        exit_nicks.difference_update(n.lower() for n in onicks)
    for nick in exit_nicks:
        if nick in track_id:
            del track_id[nick]
