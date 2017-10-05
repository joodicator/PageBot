from __future__ import print_function

from itertools import *
import traceback
import datetime
import time
import json
import re
import os.path

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
            if nick in prev_track_id and hasattr(prev_track_id[nick], 'id'):
                track_id[nick].id = util.ID(*prev_track_id[nick].id)
        prev_track_id = None
    yield refresh(bot, list(all_nicks))

#-------------------------------------------------------------------------------
# track_id[nick.lower()]
# is a Record instance, which exists only if the bot shares a channel with nick
# or if nick is the bot's own nick.
class Record(object):
    __slots__ = 'id', 'access'
    def __init__(self, id=None):
        self.id = id         # ID('nick', 'user', 'host') if known, else None.
        self.access = set()  # set of access_name.lower() granted.
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
    if os.path.exists(CREDENTIALS_FILE):
        try:
            raw_creds = util.fdict(CREDENTIALS_FILE)
            return {name.lower(): process_credentials(creds)
                    for (name,creds) in raw_creds.iteritems()}
        except Exception:
            traceback.print_exc()
    return {}    

def process_credentials(creds):
    return sorted(creds, key=lambda cred:
        0 if cred[0] == 'hostmask' else
        1 if cred[0] == 'access' else
        2 if cred[0] == 'prev_hosts' else
        3 if cred[0] == 'nickserv' else
        4)

credentials = read_credentials()

#-------------------------------------------------------------------------------
# prev_hosts[access_name.lower()]
# is a list of (unique) 'nick!user@host' which have had access to access_name,
# in chronological order with the most recent last.
def read_prev_hosts():
    new_prev_hosts = dict()
    if os.path.exists(PREV_HOSTS_FILE):
        try:
            with open(PREV_HOSTS_FILE) as file:
                new_prev_hosts = json.load(file)
        except (ValueError, IOError):
            traceback.print_exc()
    new_prev_hosts = util.recursive_encode(new_prev_hosts, 'utf-8')
    return new_prev_hosts

def write_prev_hosts(new_prev_hosts):
    try:
        data = json.dumps(new_prev_hosts, indent=4, ensure_ascii=False)
        with open(PREV_HOSTS_FILE, 'w') as file:
            file.write(data)
    except (ValueError, IOError):
        traceback.print_exc()

prev_hosts = read_prev_hosts()

#===============================================================================
# yield check_access(bot, query, name) -> True iff query has access to name.
# where query = nick or ID(nick, user, host)
@util.mfun(link, 'identity.check_access')
def check_access(bot, query, name, ret):
    name = name.lower()

    if isinstance(query, tuple):
        nick = query.nick.lower()
        id = query
    else:
        nick = query.lower()
        id = yield get_id(bot, nick)

    host = None if id is None else id_to_hostmask(id).lower()

    # If a positive result is already cached, return that result.
    if nick in track_id and name in track_id[nick].access:
        yield ret(True)
        return

    creds = credentials.get(name, list())
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
# yield get_id(bot, nick) -> ID(nick,user,host) or None
@util.mfun(link, 'identity.get_id')
def get_id(bot, nick, ret):
    result = yield get_ids(bot, [nick])
    yield ret(result[0])

RPL_WHOREPLY = '352'

# get_id_cache[nick.lower()] = (ID(nick,user,host) or None, time.time())
get_id_cache = {}

# yield get_ids(bot, [nick1, ...]) -> [ID(nick1,user1,host1) or None, ...]
# This is more efficient than multiple separate invocations of get_id.
@util.mfun(link, 'identity.get_ids')
def get_ids(bot, nicks, ret, timeout_const_s=15, timeout_linear_s=2):
    for nick, (id, ctime) in get_id_cache.items():
        now = time.time()
        if id is not None and ctime < now-10 or ctime < now-300:
            del get_id_cache[nick]

    who_nicks = []
    wait_nicks = set()
    nick_ids = {}
    for nick in nicks:
        nick = nick.lower()
        if nick in track_id and track_id[nick].id is not None:
            nick_ids[nick] = track_id[nick].id
        elif nick in get_id_cache:
            if get_id_cache[nick][0] is not None:
                nick_ids[nick] = get_id_cache[nick][0]
            else:
                wait_nicks.add(nick)
        else:
            who_nicks.append(nick)
            wait_nicks.add(nick)

    for nick in who_nicks:
        bot.send_cmd('WHO %s' % nick)
        get_id_cache[nick] = (None, time.time())

    if wait_nicks:
        lines = len(wait_nicks)
        timeout = yield runtime.timeout(timeout_const_s + lines*timeout_linear_s)
    while wait_nicks:
        event, args = yield hold(bot, RPL_WHOREPLY, timeout)
        if event == timeout: break
        _bot, _from, _to, _chan, user, host, _server, nick = args[:8]
        id = util.ID(nick, user, host)
        nick = nick.lower()
        if nick not in wait_nicks: continue
        wait_nicks.remove(nick)
        if nick in track_id:
            track_id[nick].id = id
        get_id_cache[nick] = (id, time.time())
        nick_ids[nick] = id

    for nick in who_nicks:
        if nick in get_id_cache and get_id_cache[nick][0] is None:
            del get_id_cache[nick]

    yield ret([nick_ids.get(n.lower()) for n in nicks])

#-------------------------------------------------------------------------------
# yield get_hostmask(bot, nick) -> 'nick!user@host' or None
@util.mfun(link, 'identity.get_hostmask')
def get_hostmask(bot, nick, ret):
    id = yield get_id(bot, nick)
    yield ret(None if id is None else id_to_hostmask(id))

# yield get_hostmasks(bot, [nick1, ...]) -> ['nick1!user1@host1' or None, ..]
# This is more efficient than multiple separate invocations of get_hostmask.
def get_hostmasks(bot, nicks, ret):
    ids = yield get_ids(bot, nicks)
    yield ret([None if id is None else id_to_hostmask(id) for id in ids])

#-------------------------------------------------------------------------------
# hostmask_to_id('nick!user@host') = ID('nick', 'user', 'host')
def hostmask_to_id(hostmask):
    return util.ID(*re.match(r'(.*)!(.*)@(.*)$', hostmask).groups())

# id_to_hostmask(ID('nick', 'user', 'host')) = 'nick!user@host'
def id_to_hostmask(id):
    return '%s!%s@%s' % id

#-------------------------------------------------------------------------------
# yield refresh(bot, nicks) -> re-check certain credentials for each nick.
@util.msub(link, 'identity.refresh')
def refresh(bot, nicks):
    nicks = map(str.lower, nicks)

    ids = yield get_ids(bot, nicks, timeout_const_s=240)
    for nick, id in izip(nicks, ids):
        if id is None or nick not in track_id: continue
        track_id[nick].id = id

    ns_nick_access = dict()
    for access_name, creds in credentials.iteritems():
        granted_nicks = set()
        for cred in creds:
            if cred[0] == 'hostmask' and len(cred) > 1:
                for id in ids:
                    if id is None or id.nick.lower() in granted_nicks: continue
                    hostmask = id_to_hostmask(id)
                    if re.match(util.wc_to_re(cred[1]), hostmask, re.I):
                        yield grant_access(bot, id, access_name)
                        granted_nicks.add(id.nick.lower())

            elif cred[0] == 'prev_hosts' and len(cred) > 1:
                for id in ids:
                    if id is None or id.nick.lower() in granted_nicks: continue
                    if access_name.lower() not in prev_hosts: continue
                    userhost = '%s@%s' % (id.user, id.host)
                    if userhost in prev_hosts[access_name][-cred[1]]:
                        yield grant_access(bot, id, access_name)
                        granted_nicks.add(id.nick.lower())

            elif cred[0] == 'nickserv' and len(cred) > 1:
                cred_nick = cred[1].lower()
                if cred_nick not in nicks: continue
                if cred_nick in granted_nicks: continue
                access_names = ns_nick_access.get(cred_nick, [])
                if access_name.lower() in access_names: continue
                ns_nick_access[cred_nick] = access_names + [access_name.lower()]

    status = yield nickserv.statuses(bot, ns_nick_access.keys())
    for nick, access_names in ns_nick_access.iteritems():
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
            id = yield get_id(bot, nick)
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

# yield enum_access(bot, access_name) -> [nick1, nick2, ...]
# A sequence of nicks which can be found currently online and authenticated to
# the given access name. Cached authentication records and static 'known_as'
# records are used as a heuristic for the search.
@util.mfun(link, 'identity.enum_access')
def enum_access(bot, access_name, ret):
    access_name = access_name.lower()
    nicks = set()
    for nick, record in track_id.iteritems():
        if access_name in record.access:
            nicks.add(nick)
    for nick in known_as(access_name):
        nick = nick.lower()
        access = yield check_access(bot, nick, access_name)
        if access:
            nicks.add(nick)
    yield ret(tuple(nicks))

# A sequence of nicks by which the given access name is known, according to
# 'known_as' records in the credentials file, but which are not necessarily
# online or authenticated to the given access name.
def known_as(access_name):
    return tuple(nick
        for cred in credentials.get(access_name.lower(), ())
        if cred[0] == 'known_as' and len(cred) > 1
        for nick in cred[1])

#===============================================================================
@link('NAMES_SYNC')
def h_names_sync(bot, chan, chan_nicks, chan_umodes):
    # Upon receiving the nick list for a channel, create identity-tracking
    # records for any previously unknown nicks in the channel.
    for nick in chan_nicks:
        if nick.lower() not in track_id:
            track_id[nick.lower()] = Record()
    if chan_nicks:
        yield refresh(bot, chan_nicks)

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    # Create an identity-tracking record.
    nick = id.nick.lower()
    if nick not in track_id:
        track_id[nick] = Record()
    track_id[nick].id = id
    yield refresh(bot, [nick])

@link('SELF_NICK',  a=lambda bot,     new_nick: (None, bot.nick, new_nick))
@link('OTHER_NICK', a=lambda bot, id, new_nick: (id,   id.nick,  new_nick))
def h_other_nick(bot, *args, **kwds):
    # Rename any identity-tracking record.
    id, old_nick, new_nick = kwds.pop('a')(bot, *args, **kwds)
    if old_nick.lower() in track_id:
        record = track_id.pop(old_nick.lower())
        if id is None and record.id:
            id = record.id
        if id is not None:
            record.id = util.ID(new_nick, id.user, id.host)
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
