from collections import defaultdict
import re

from untwisted.magic import sign

import util
link, install, uninstall = util.LinkSet().triple()

names_channels = defaultdict(list)
track_channels = defaultdict(list)

def reload(prev):
    names_channels.update(prev.names_channels)
    track_channels.update(prev.track_channels)    

def strip_names(names):
    return [re.sub(r'^[+%@~^]', '', n) for n in names]

def names(bot, chan):
    return util.mcall('channel.names', bot, chan.lower())

@link('channel.names')
def h_names(bot, chan):
    bot.send_cmd('NAMES %s' % chan)


@link('353')
def h_rpl_namereply(bot, _1, _2, _3, chan, names):
    names = re.findall(r'\S+', names)
    names_channels[chan] += names

    track_names = track_channels[chan.lower()]
    for name in strip_names(names):
        if name.lower() in map(str.lower, track_names): continue
        track_names.append(name)
    track_channels[chan.lower()] = track_names

@link('366')
def h_rpl_endofnames(bot, _1, _2, chan, *args):
    yield sign(('channel.names', bot, chan.lower()), names_channels[chan])
    del names_channels[chan]


@link('SOME_JOIN')
def h_self_join(bot, id, chan):
    chan = chan.lower()
    names = track_channels[chan]
    if id.nick.lower() in map(str.lower, names): return
    names.append(id.nick)
    track_channels[chan] = names

@link('SELF_PART')
@link('SELF_KICKED')
@link('SELF_QUIT_CHAN')
def h_self_part_kicked_quit(bot, chan, *args):
    del track_channels[chan.lower()]

@link('OTHER_PART')
def h_other_part(bot, id, chan, *args):
    chan = chan.lower()
    names = track_channels[chan]
    names = [n for n in names if n.lower() != id.nick.lower()]
    track_channels[chan] = names

@link('OTHER_KICKED')
def h_other_kicked(bot, nick, op_id, chan, *args):
    chan = chan.lower()
    names = track_channels[chan]
    names = [n for n in names if n.lower() != nick.lower()]
    track_channels[chan] = names

@link('SELF_QUIT')
def h_self_quit(bot, msg):
    for chan, names in track_channels.iteritems():
        yield sign('SELF_QUIT_CHAN', bot, chan, msg)
        yield sign(('SELF_QUIT_CHAN', chan), bot, msg)

@link('OTHER_QUIT')
def h_other_quit(bot, id, msg):
    for chan, names in track_channels.iteritems():
        if id.nick.lower() not in map(str.lower, names): continue
        names = [n for n in names if n.lower() != id.nick.lower()]  
        track_channels[chan] = names
        yield sign('OTHER_QUIT_CHAN', bot, id, chan, msg)
        yield sign(('OTHER_QUIT_CHAN', chan), bot, id, msg)

@link('SOME_NICK')
def h_other_nick(bot, id, new_nick):
    old_nick = id.nick.lower()
    for chan, names in track_channels.iteritems():
        if old_nick not in map(str.lower, names): continue
        names = map(lambda n: new_nick if n.lower() == old_nick else n, names)
        track_channels[chan] = names
        yield sign('SOME_NICK_CHAN', bot, id, new_nick, chan)
        yield sign(('SOME_NICK_CHAN', chan), bot, id, new_nick)
        if old_nick != bot.nick.lower():
            yield sign('OTHER_NICK_CHAN', bot, id, new_nick, chan)
            yield sign(('OTHER_NICK_CHAN', chan), bot, id, new_nick)

@link('CLOSING')
def h_closing(bot):
    for chan, names in track_channels.iteritems():
        yield sign('CLOSING_CHAN', bot, chan)
        yield sign(('CLOSING_CHAN', chan), bot)
