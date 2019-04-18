from collections import defaultdict
from itertools import *
import inspect
import re

from untwisted.magic import sign, hold

import util
link, install, uninstall = util.LinkSet().triple()


ERR_NOTONCHAN   = '442'
ERR_CHOPNEEDED  = '482'
ERR_NOSUCHCHAN  = '403'
RPL_NOTOPIC     = '331'
RPL_TOPIC       = '332'
RPL_CHANMODEIS  = '324'
RPL_NAMEREPLY   = '353'
RPL_ENDOFNAMES  = '366'

# names_channels[chan.lower()]
# list of NAMES query results collected so far, including prefixes.
names_channels = defaultdict(list)

# track_channels[chan.lower()]
# list of nicks known to be in chan.
track_channels = defaultdict(list)

# umode_channels[chan.lower()][nick.lower()]
# string of modes that nick is known to have on chan.
umode_channels = defaultdict(dict)

# cmode_channels[chan.lower()][mode_char]
# set if mode_char is set on chan; None if set with no parameter; else, a string.
cmode_channels = defaultdict(dict)

# topic_channels[chan.lower()]
# the topic in channel, or None if there is no topic.
topic_channels = dict()

# capitalisation[chan.lower()]
# the canonical capitalisation of chan, according to certain server messages.
capitalisation = dict()

def hard_reload(prev):
    reload(prev, hard=True)

def reload(prev, hard=False):
    if hasattr(prev,'track_channels') and isinstance(prev.track_channels,dict):
        track_channels.update(prev.track_channels)
    if hasattr(prev,'umode_channels') and isinstance(prev.umode_channels,dict):
        umode_channels.update(prev.umode_channels)
    if hasattr(prev,'cmode_channels') and isinstance(prev.cmode_channels,dict):
        cmode_channels.update(prev.cmode_channels)
    if hard: return

    if hasattr(prev,'names_channels') and isinstance(prev.names_channels,dict):
        names_channels.update(prev.names_channels)
    if hasattr(prev,'topic_channels') and isinstance(prev.topic_channels,dict):
        topic_channels.update(prev.topic_channels)
    if hasattr(prev,'capitalisation') and isinstance(prev.capitalisation,dict):
        capitalisation.update(prev.capitalisation)

#===============================================================================
# Provision of TOPIC query.
def topic(bot, chan):
    return util.mcall('channel.topic', bot, chan)

@link('channel.topic')
def h_topic(bot, chan):
    ret = lambda r: sign(('channel.topic', bot, chan), r)
    # Return the cached topic if it exists.
    if chan.lower() in topic_channels:
        yield ret(topic_channels[chan.lower()])
        return
    # Otherwise, retrieve the topic from the server.
    bot.send_cmd('TOPIC %s' % chan)
    while True:
        (event, data) = yield hold(bot, ERR_NOTONCHAN, 'CHAN_TOPIC')
        if event == 'CHAN_TOPIC':
            e_bot, e_chan, e_topic = data[:3]
            if e_chan.lower() != chan.lower(): continue
            yield ret(e_topic)
        else:
            e_bot, e_src, e_tgt, e_chan = data[:4]
            if e_chan.lower() != chan.lower(): continue
            yield ret(None)
        break

@link(RPL_TOPIC,   a=lambda src, tgt, chan, topic: (chan, topic))
@link(RPL_NOTOPIC, a=lambda src, tgt, chan, *args: (chan, None))
@link('TOPIC',     a=lambda src, chan, topic:      (chan, topic))
def h_rpl_topic(bot, *args, **kwds):
    chan, topic = kwds['a'](*args)
    yield sign('CHAN_TOPIC', bot, chan, topic)

#===============================================================================
# Provision of MODE query.
def mode(bot, chan):
    return util.mcall('channel.mode', bot, chan)

@link('channel.mode')
def h_mode(bot, chan):
    ret = lambda r: sign(('channel.mode', bot, chan), r)
    # Return the cached mode if it exists.
    if chan.lower() in cmode_channels:
        yield ret(cmode_channels[chan.lower()])
        return
    # Otherwise, retrieve the mode from the server.
    bot.send_cmd('MODE %s' % chan)
    while True:
        event, data = yield hold(bot,
            ERR_NOTONCHAN, ERR_NOSUCHCHAN, 'CHAN_MODE_SYNC')
        if event == 'CHAN_MODE_SYNC':
            e_bot, e_chan, e_mode = data[:3]
            if e_chan.lower() != chan.lower(): continue
            yield ret(e_mode)
        else:
            e_bot, e_src, e_tgt, e_chan = data[:4]
            if e_chan.lower() != chan.lower(): continue
            yield ret(None)
        break

@link(RPL_CHANMODEIS)
def h_rpl_chanmodeis(bot, src, tgt, chan, *args):
    yield sign('CHAN_MODE_IS', bot, chan, parse_mode(bot, *args))

@link('MODE')
def h_mode(bot, src, chan, *args):
    if not chan.startswith('#'): return
    yield sign('CHAN_MODE', bot, src, chan, parse_mode(bot, *args))

# Given a list of arguments to MODE or RPL_CHANMODEIS, returns a list of tuples
# ('+',m,arg) or ('-',m,arg) where m is a mode character, and arg may be None.
def parse_mode(bot, *args):
    modes, params = [], []
    for arg in args:
        if re.match(r'[+-]', arg):
            for part in re.finditer(r'(?P<pm>[+-])(?P<ms>[^+-]*)', arg):
                modes.extend((part.group('pm'), m) for m in part.group('ms'))
        else:
            params.append(arg)
    
    # See http://www.irc.org/tech_docs/draft-brocklesby-irc-isupport-03.txt
    adr_ms, par_ms, set_ms, nul_ms = bot.isupport['CHANMODES']
    pre_ms, pre_cs = bot.isupport['PREFIX']
    pmodes = []
    for pm, m in modes:
        if m in (adr_ms + par_ms + pre_ms) or m in set_ms and pm=='+':
            param = params.pop(0) if params else None
        else:
            param = None
        pmodes.append((pm, m, param))
    return pmodes

#===============================================================================
# Provision of NAMES query.
def names(bot, chan, include_prefix=True):
    return util.mcall('channel.names', bot, chan, include_prefix)

@link('channel.names')
def h_names(bot, chan, include_prefix):
    if chan.lower() in track_channels and chan.lower() in umode_channels:
        # Return the cached names if they exist.
        nicks = track_channels[chan.lower()]
        umode = umode_channels[chan.lower()]
    else:
        # Otherwise, retrieves the names from the server.
        bot.send_cmd('NAMES %s' % chan)
        while True:
            event, data = yield hold(bot, 'NAMES_SYNC')
            e_bot, e_chan, nicks, umode = data
            if e_chan.lower() == chan.lower(): break
    # Reconstruct the nick prefixes from the nicks and their modes.
    pre_ms, pre_cs = bot.isupport['PREFIX']
    names = []
    for nick in nicks:
        for pre_m, pre_c in izip(pre_ms, pre_cs):
            if pre_m in umode.get(nick.lower(), ''):
                prefix, sort_key = pre_c, (-pre_cs.index(pre_c), nick.lower())
                break
        else:
            prefix, sort_key = '', (None, nick.lower())
        names.append((sort_key, prefix+nick if include_prefix else nick))
    names = [n for (_,n) in sorted(names, reverse=True)]
    yield sign(('channel.names', bot, chan, include_prefix), names)

@link(RPL_NAMEREPLY)
def h_rpl_namereply(bot, _1, _2, _3, chan, names):
    names = re.findall(r'\S+', names)
    names_channels[chan.lower()] += names

@link(RPL_ENDOFNAMES)
def h_rpl_endofnames(bot, _1, _2, chan, *args):
    names = names_channels[chan.lower()]
    yield sign('NAMES', bot, chan, names)
    del names_channels[chan.lower()]

# Strips channel-mode prefixes from a list of nicks returned by NAMES.
# e.g. ['@n1', '+n2', 'n3'] -> ['n1', 'n2', 'n3']
def strip_names(bot, names):
    return [split_name(bot,n)[1] for n in names]

# Splits a nick returned by NAMES into its prefix(es) and its main part.
# e.g. '@n1' -> '@', 'n1'
def split_name(bot, name):
    modes, prefs = bot.isupport['PREFIX']
    r = r'(?P<pre>[%s]*)(?P<nick>.*)' % re.escape(prefs)
    return re.match(r, name).group('pre', 'nick')

# Adds a suitable prefix to "nick" based on the modes it possesses in "chan".
# e.g. 'n1', '#n1' -> '@n1'
def prefix_nick(bot, nick, chan):
    modes = umode_channels[chan.lower()].get(nick.lower(), '')
    return modes_prefix_nick(bot, nick, modes)

# As `prefix_nick', but takes a sequence of channel user modes instead of
# a channel.
def modes_prefix_nick(bot, nick, modes):
    pre_ms, pre_cs = bot.isupport['PREFIX']
    for pre_m, pre_c in izip(pre_ms, pre_cs):
        if pre_m in modes: return pre_c + nick
    return nick

# Returns True if (according to current records) "nick" has a channel mode
# matching "op", or greater in power than "op", according to the ISUPPORT PREFIX
# record of the server (and some additional heuristics); or otherwise False.
def has_op_in(bot, nick, chan, op='o'):
    modes = umode_channels[chan.lower()].get(nick.lower(), '')
    return modes_has_op_in(bot, modes, op=op)

# As `has_op_in', but takes a sequence of channel user modes rather than a nick.
def modes_has_op_in(bot, modes, op='o'):
    pre_ms, pre_cs = bot.isupport['PREFIX']

    if op in pre_ms:
        return any(pre_ms.index(um) <= pre_ms.index(op) for um in modes)

    alt_pre_ms = 'qohv'
    if op in alt_pre_ms:
        op_ix = alt_pre_ms.index(op)
        return any(
            pre_ms.index(um) <= pre_ms.index(om)
            for om in alt_pre_ms[:op_ix] if om in pre_ms
            for um in modes)

    return False

#===============================================================================
# Updating channel data.

@link('NAMES')
def h_names(bot, chan, new_names):
    chan = chan.lower()
    track_names = track_channels[chan]
    umode_names = umode_channels[chan]

    pre_ms, pre_cs = bot.isupport['PREFIX']
    for prefix, nick in (split_name(bot,n) for n in new_names):
        # Update track_channels
        if nick.lower() not in map(str.lower, track_names):
            track_names.append(nick)
        elif nick not in track_names:
            track_names = [n for n in track_names if n.lower() != nick.lower()]
            track_names.append(nick)

        # Update umode_channels
        if len(prefix)==1 and nick.lower() in umode_names and prefix in pre_cs:
            # Add the mode and remove all known higher modes.
            i = pre_cs.index(prefix)
            umode_names[nick.lower()] = pre_ms[i] + ''.join(
                m for m in umode_names[nick.lower()] if m not in pre_ms[:i])
        else:
            # Set to exactly the given modes.
            umode_names[nick.lower()] = ''.join(
                m for c in prefix if c in pre_cs
                  for i in [pre_cs.index(c)]
                  for m in pre_ms[i:i+1])

    track_channels[chan] = track_names
    umode_channels[chan] = umode_names
    yield sign('NAMES_SYNC', bot, chan, track_names, umode_names)

@link('CHAN_TOPIC')
def h_chan_topic(bot, chan, topic):
    topic_channels[chan.lower()] = topic

@link('CHAN_MODE_IS', a=lambda      ch, ms: (ch, ms, True))
@link('CHAN_MODE',    a=lambda src, ch, ms: (ch, ms, False))
def h_mode_is_change(bot, *args, **kwds):
    chan, modes, sync = kwds['a'](*args)
    chan = chan.lower()

    if sync and chan in cmode_channels:
        del cmode_channels[chan]
    cmodes = cmode_channels[chan]
    umodes = umode_channels[chan]

    adr_ms, par_ms, set_ms, nul_ms = bot.isupport['CHANMODES']
    pre_ms, pre_cs = bot.isupport['PREFIX']
    for (pm, m, param) in modes:
        if m in pre_ms:
            # Set or unset a channel user-mode on a certain nick.
            umode = umodes.get(param.lower(), '')
            if pm == '+' and m not in umode:
                umode += m
            elif pm == '-' and m in umode:
                umode = ''.join(um for um in umode if um != m)
            umodes[param.lower()] = umode
        elif m in adr_ms:
            # Set or unset a channel mode on a certain hostmask.
            cmode = cmodes.get(m, [])
            if type(cmode) is not list: cmode = []
            if pm == '+':
                if param.lower() not in map(str.lower, cmode): cmode.append(param)
            elif pm == '-':
                cmode = [ad for ad in cmode if ad.lower() != param.lower()]
            cmodes[m] = cmode
        else:
            # Set or unset a channel mode with 0 or 1 parameters.
            if pm == '+':
                cmodes[m] = param
            elif pm == '-' and m in cmodes:
                del cmodes[m]
            
    cmode_channels[chan] = cmodes
    umode_channels[chan] = umodes

    if sync:
        yield sign('CHAN_MODE_SYNC', bot, chan, cmodes)

@link('SELF_JOIN')
def h_self_join(bot, chan):
    capitalisation[chan.lower()] = chan

@link('SOME_JOIN')
def h_some_join(bot, id, chan):
    names = track_channels[chan.lower()]
    if id.nick.lower() in map(str.lower, names): return
    names.append(id.nick)
    track_channels[chan.lower()] = names

@link('SOME_NICK_CHAN_FINAL')
def h_some_nick_chan(bot, id, new_nick, chan):
    chan, old_nick = chan.lower(), id.nick.lower()
    if chan in track_channels:
        names = track_channels[chan]
        names = [(new_nick if n.lower() == old_nick else n) for n in names]
        track_channels[chan] = names
    if chan in umode_channels and old_nick in umode_channels[chan]:
        umode_channels[chan][new_nick.lower()] = umode_channels[chan].pop(old_nick)

@link('OTHER_PART_FINAL',      a=lambda id, chan, msg:          (id.nick, chan))
@link('OTHER_KICKED_FINAL',    a=lambda knick, opid, chan, msg: (knick, chan))
@link('OTHER_QUIT_CHAN_FINAL', a=lambda id, msg, chan:          (id.nick, chan))
def h_other_exit_chan(bot, *args, **kwds):
    nick, chan = map(str.lower, kwds['a'](*args))
    if chan in track_channels:
        names = track_channels[chan]
        names = [n for n in names if n.lower() != nick]
        track_channels[chan] = names
    if chan in umode_channels and nick in umode_channels[chan]:
        del umode_channels[chan][nick]

@link('SELF_PART_FINAL')
@link('SELF_KICKED_FINAL')
def h_self_part_kicked_final(bot, chan, *args):
    chan = chan.lower()
    if chan in track_channels: del track_channels[chan]
    if chan in umode_channels: del umode_channels[chan]
    if chan in cmode_channels: del cmode_channels[chan]
    if chan in topic_channels: del topic_channels[chan]

#===============================================================================
# Rebroadcast channel-specific events.

@link('OTHER_QUIT', e='OTHER_QUIT_CHAN', a=lambda id, msg:   id)
@link('SOME_NICK',  e='SOME_NICK_CHAN',  a=lambda id, nnick: id)
@link('OTHER_NICK', e='OTHER_NICK_CHAN', a=lambda id, nnick: id)
@link('CLOSING',    e='CLOSING_CHAN',    a=lambda:           None)
def h_general(bot, *args, **kwds):
    e, id = kwds['e'], kwds['a'](*args)
    for chan, names in track_channels.iteritems():
        if id and id.nick.lower() not in map(str.lower, names): continue
        eargs = args + (chan,)
        yield sign(e,            bot, *eargs)
        yield sign(e + '_FINAL', bot, *eargs)

#===============================================================================
# Management of "quiet" channels.

try:
    with open('conf/quiet_channels.txt') as file:
        chans = re.findall(r'\S+', file.read())
        quiet_channels_list = map(str.lower, chans)
except IOError:
    quiet_channels_list = []

# Returns a list of lowercase channel (including any '#' prefixes) name in
# which the bot is configured to be particuarly quiet.
def quiet_channels():
    return quiet_channels_list

# A function decorated with @not_quiet(chan_arg=a) will do nothing if it is
# called with the argument named a set to a channel either in quiet_channels()
# or with mode +m.
def not_quiet(chan_arg='target'):
    def not_quiet_deco(func):
        def not_quiet_func(*args, **kwds):
            cargs = inspect.getcallargs(func, *args, **kwds)
            chan = cargs[chan_arg]
            modes = cmode_channels.get(chan)
            if modes and 'm' in modes: return
            if type(chan) is str and chan.lower() in quiet_channels(): return
            if kwds.get('quiet', False): return
            return func(*args, **kwds)
        return not_quiet_func
    return not_quiet_deco
