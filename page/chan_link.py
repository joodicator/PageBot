#===============================================================================
# chan_link.py - allows pairs of channels to be linked together such that events
# in one channel are broadcast to the other, and vice versa.

import inspect
import re

import auth
import util
import channel
import message

link, install, uninstall = util.LinkSet().triple()

# c2.lower() in links[c1.lower()] iff c1 is broadcast to c2.
links = dict()

# c1.lower() in decay_links if c1's link will eventually decay.
decay_links = set()

def reload(prev):
    if hasattr(prev, 'links') and isinstance(prev.links, dict):
        links.update(prev.links)
    if hasattr(prev, 'decay_links') and isinstance(prev.decay_links, set):
        for decay_chan in prev.decay_links:
            if decay_chan not in links: continue
            decay_links.add(decay_chan)

# Establish a mutual link between channels c1 and c2.
# If an existing link is marked to decay, unmark it.
def add_link(*args):
    return util.sub(h_add_link(*args))

def h_add_link(bot, c1, c2):
    c1, c2 = c1.lower(), c2.lower()
    if c1 not in links: links[c1] = set()
    if c2 not in links: links[c2] = set()

    if c2 not in links[c1] or c1 not in links[c2]:
        links[c1].add(c2)
        links[c2].add(c1)
        decay_links.discard(c1)
        decay_links.discard(c2)
        yield introduce(bot, c1, c2)
        yield introduce(bot, c2, c1)

# Delete any link between channels c1 and c2.
def del_link(*args):
    return util.sub(h_del_link(*args))

def h_del_link(bot, c1, c2):
    c1, c2 = c1.lower(), c2.lower()
    if c1 in links:
        links[c1].discard(c2)
        if not links[c1]: del links[c1]
    if c2 in links:
        links[c2].discard(c1)
        if not links[c2]: del links[c2]
    decay_links.discard(c1)
    decay_links.discard(c2)
    bot.send_msg(c1, '%s: Disconnected from channel.' % c2)
    bot.send_msg(c2, '%s: Disconnected from channel.' % c1)

# Mark an existing link so that it will eventually be removed
# if it is not refreshed by calling add_link().
def decay_link(bot, c1, c2):
    decay_links.add(c1)
    decay_links.add(c2)

# Return 0 if channels c1 and c2 are not linked,
#    or -1 if they are linked, but marked to decay,
#    or  1 if they are linked and not marked to decay.
def is_linked(c1, c2):
    c1, c2 = c1.lower(), c2.lower()
    if  (c1 not in links or c2 not in links[c1]) \
    and (c2 not in links or c1 not in links[c2]):
        return 0
    elif c1 in decay_links or c2 in decay_links:
        return -1
    else:
        return 1

#===============================================================================
@util.msub(link, 'chan_link.introduce')
def introduce(bot, chan, lchan):
    topic, names = yield util.mmcall_all(bot,
        ('channel.topic', bot, chan),
        ('channel.names', bot, chan, True))
    if topic:
        bot.send_msg(lchan, '%s: Topic: %s' % (chan, topic), no_link=True)
    for row in util.join_cols(*(names[i::9] for i in range(9))):
        bot.send_msg(lchan, '%s: Users: \2%s\2' % (chan, row), no_link=True)

@link('SELF_JOIN')
def h_self_join(bot, chan):
    if chan.lower() not in links: return
    for lchan in links[chan.lower()]:
        yield introduce(bot, chan, lchan)

@link('SELF_PART')
@link('SELF_KICKED')
def h_self_exit(bot, chan, *args):
    chan = chan.lower()
    if chan not in links: return
    if chan not in decay_links: return
    for lchan in list(links[chan]):
        if lchan.lower() in channel.track_channels: continue
        yield del_link(bot, chan, lchan)

@link('!online')
def h_online(bot, id, chan, args, full_msg):
    for linked_chan in links.get(chan.lower(), set()):
        yield introduce(bot, linked_chan, chan)
        yield introduce(bot, chan, linked_chan)

@link('!add-chan-link')
@auth.admin
def h_add_chan_link(bot, id, chan, args, full_msg):
    if not chan or not re.match(r'#\S*$', args):
        message.reply(bot, id, chan, 'Error: invalid argument: "%s".' % args)
    else:
        yield add_link(bot, chan, args)

@link('!del-chan-link')
@auth.admin
def h_del_chan_link(bot, id, chan, args, full_msg):
    if not chan or not re.match(r'#\S*$', args):
        message.reply(bot, id, chan, 'Error: invalid argument: "%s".' % args)
    else:
        yield del_link(bot, chan, args)

#===============================================================================
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: \2%s\2 [%s@%s] has joined.' % (chan, id.nick, id.user, id.host)
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('SOME_PART')
def h_other_part(bot, id, chan, pmsg):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s has left%s' % (chan, id.nick, ': %s' % pmsg if pmsg else '.')
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('SOME_KICKED')
def h_other_kicked(bot, knick, op_id, chan, kmsg):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s was kicked by %s%s' % (
        chan, knick, op_id.nick, ': %s' % kmsg if kmsg else '.')
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('OTHER_QUIT_CHAN')
def h_other_quit_chan(bot, id, qmsg, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s has quit%s' % (chan, id.nick, ': %s'%qmsg if qmsg else '.')
    for lchan in links[chan.lower()]:
        lnicks = yield channel.names(bot, lchan, include_prefix=False)
        if id.nick.lower() in map(str.lower, lnicks): continue
        bot.send_msg(lchan, msg, no_link=True)

@link('OTHER_NICK_CHAN')
def h_other_nick_chan(bot, id, nnick, chan):
    if chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s is now known as \2%s\2.' % (chan, id.nick, nnick)
    for lchan in links[chan.lower()]:
        lnicks = yield channel.nicks(bot, lchan)
        if id.nick.lower() in map(str.lower, lnicks): continue
        bot.send_msg(lchan, msg, no_link=True)

@link('MESSAGE',  a=lambda bot, id, chan, msg:
                    (bot, id.nick, chan, msg))
@link('COMMAND',  a=lambda bot, id, chan, event, body, msg:
                    (bot, id.nick, chan, msg))
@link('SEND_MSG', a=lambda bot, chan, msg, kwds:
                    (bot, bot.nick, not kwds.get('no_link') and chan, msg))
def h_message(*args, **kwds):
    bot, nick, chan, msg = kwds['a'](*args)
    if not chan or chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    p_nick = channel.prefix_nick(bot, nick, chan)
    match = re.match(r'\x01ACTION (?P<act>.*?)\x01?$', msg)
    msg = '%s: * %s %s' % (chan, nick, match.group('act')) if match else \
          '%s: <%s> %s' % (chan, p_nick, msg)
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('TOPIC')
def h_topic(bot, source, chan, topic):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = source.nick
    msg = '%s: %s set topic to: %s' % (source, topic) if topic else \
          '%s: %s unset the topic.' % source
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('MODE')
def h_chan_mode(bot, source, chan, *args):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = source[0]
    msg = '%s set mode: %s' % (source, ' '.join(args))
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)
