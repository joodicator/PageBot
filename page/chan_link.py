#===============================================================================
# chan_link.py - allows pairs of channels to be linked together such that events
# in one channel are broadcast to the other, and vice versa.

import inspect
import re

import util
import channel

link, install, uninstall = util.LinkSet().triple()

# c2.lower() in links[c1.lower()] iff c1 is broadcast to c2.
links = dict()

def reload(prev):
    if not hasattr(prev, 'links'): return
    if not isinstance(prev.links, dict): return
    links.update(prev.links)

# Establish a mutual link between channels c1 and c2.
def add_link(*args):
    return util.sub(h_add_link(*args))

def h_add_link(bot, c1, c2):
    c1, c2 = c1.lower(), c2.lower()
    if c1 not in links: links[c1] = set()
    if c2 not in links: links[c2] = set()
    links[c1].add(c2)
    links[c2].add(c1)
    yield introduce(bot, c1, c2)
    yield introduce(bot, c2, c1)

# Delete any link between channels c1 and c2.
def del_link(*args):
    return util.sub(h_del_link(*args))

def h_del_link(bot, c1, c2, u=False):
    c1, c2 = c1.lower(), c2.lower()
    if c1 in links:
        links[c1].discard(c2)
        if not links[c1]: del links[c1]
    if c2 in links:
        links[c2].discard(c1)
        if not links[c2]: del links[c2]

# Return True if channels c1 and c2 are linked, or otherwise False.
def is_linked(c1, c2):
    c1, c2 = c1.lower(), c2.lower()
    return c1 in links and c2 in links[c1] \
        or c2 in links and c1 in links[c2]

#===============================================================================
def introduce(*args):
    return util.sub(h_introduce(*args))

def h_introduce(bot, chan, lchan):
    topic, names = yield util.mmcall_all(bot,
        ('channel.topic', bot, chan),
        ('channel.names', bot, chan, True))
    bot.send_msg(lchan, '%s: Topic: %s' % (chan, topic))
    for row in util.join_cols(*(names[i::9] for i in range(9))):
        bot.send_msg(lchan, '%s: Users: \2%s\2' % (chan, row))

#===============================================================================
@link('SELF_JOIN')
def h_self_join(bot, chan):
    if chan.lower() not in links: return
    for lchan in links[chan.lower()]:
        yield introduce(bot, chan, lchan)

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: \2%s\2 [%s@%s] has joined.' % (chan, id.nick, id.user, id.host)
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg)

@link('SOME_PART')
def h_other_part(bot, id, chan, pmsg):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s has left%s' % (chan, id.nick, ': %s' % pmsg if pmsg else '.')
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg)

@link('SOME_KICKED')
def h_other_kicked(bot, knick, op_id, chan, kmsg):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s was kicked by %s%s' % (
        chan, knick, op_id.nick, ': %s' % kmsg if kmsg else '.')
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg)

@link('OTHER_QUIT_CHAN')
def h_other_quit_chan(bot, id, qmsg, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s has quit%s' % (chan, id.nick, ': %s'%qmsg if qmsg else '.')
    for lchan in links[chan.lower()]:
        lnicks = yield channel.nicks(bot, lchan)
        if id.nick.lower() in map(str.lower, lnicks): continue
        bot.send_msg(lchan, msg)

@link('OTHER_NICK_CHAN')
def h_other_nick_chan(bot, id, nnick, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s is now known as \2%s\2.' % (chan, id.nick, nnick)
    for lchan in links[chan.lower()]:
        lnicks = yield channel.nicks(bot, lchan)
        if id.nick.lower() in map(str.lower, lnicks): continue
        bot.send_msg(lchan, msg)

@link('MESSAGE')
def h_message(bot, id, chan, msg):
    if not chan or chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    nick = channel.prefix_nick(bot, id.nick, chan)
    match = re.match(r'\x01ACTION (?P<act>.*?)\x01?$', msg)
    msg = '%s: * %s %s' % (chan, id.nick, match.group('act')) if match else \
          '%s: <%s> %s' % (chan, nick, msg)
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg)

@link('TOPIC')
def h_topic(bot, source, chan, topic):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = '%s!%s@%s' % source
    msg = '%s set topic to: %s' % (id.nick, topic) if topic else \
          '%s unset the topic.' % (id.nick, topic)
    for chan in links[chan.lower()]: bot.send_msg(lchan, msg)

@link('MODE')
def h_chan_mode(bot, source, chan, *args):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = source[0]
    msg = '%s set mode: %s' % (source, ' '.join(args))
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg)
