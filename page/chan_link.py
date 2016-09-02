#===============================================================================
# chan_link.py - allows pairs of channels to be linked together such that events
# in one channel are broadcast to the other, and vice versa.

import inspect
import re

from untwisted.magic import sign

import auth
import util
import channel
import message

LINKS_FILE = 'state/chan_link_persistent.txt'

link, link_install, uninstall = util.LinkSet().triple()

# c2.lower() in links[c1.lower()] iff c1 is broadcast to c2.
links = dict()

# c1.lower() in decay_links if c1's link will eventually decay.
decay_links = set()

# (c1.lower(), c2.lower()) in persistent_links if a link from c1 to c2
# will be created upon the next restart.
try:
    persistent_links = set(util.read_list(LINKS_FILE))
except IOError:
    persistent_links = set()

def install(bot):
    for c1, c2 in persistent_links:
        c1, c2 = c1.lower(), c2.lower()
        if c1 not in links: links[c1] = set()
        links[c1].add(c2)
    link_install(bot)

def reload(prev):
    if hasattr(prev, 'links') and isinstance(prev.links, dict):
        links.update(prev.links)
    if hasattr(prev, 'decay_links') and isinstance(prev.decay_links, set):
        for decay_chan in prev.decay_links:
            if decay_chan not in links: continue
            decay_links.add(decay_chan)

def add_persistent_link(c1, c2):
    persistent_links.add((c1.lower(), c2.lower()))
    util.write_list(LINKS_FILE, list(persistent_links))

def del_persistent_link(c1, c2):
    persistent_links.discard((c1.lower(), c2.lower()))
    util.write_list(LINKS_FILE, list(persistent_links))

# Establish a link from channel c1 to c2, and from c2 to c1 if mutual is True.
# If an existing link is marked to decay, unmark it. If persistent is True,
# the link will be saved in a state file to be restored after any restart.
@util.msub(link, 'chan_link.add_link')
def add_link(bot, c1, c2, mutual=True, persistent=False):
    c1, c2 = c1.lower(), c2.lower()   
    if c1 not in links: links[c1] = set()
    if c2 not in links[c1] or c1 not in links[c2]:
        add_persistent_link(c1, c2)
        links[c1].add(c2)
        decay_links.discard(c1)
        yield introduce(bot, c1, c2)
    if mutual:
        yield add_link(bot, c2, c1, False, persistent)

# Delete any link between channels c1 and c2.
@util.msub(link, 'chan_link.del_link')
def del_link(bot, c1_orig, c2_orig):
    c1, c2 = c1_orig.lower(), c2_orig.lower()
    notify_c1 = notify_c2 = False
    if c1 in links:
        if c2 in links[c1]:
            del_persistent_link(c1, c2)
            notify_c2 = True
            links[c1].remove(c2)
        if not links[c1]: del links[c1]
    if c2 in links:
        if c1 in links[c2]:
            del_persistent_link(c2, c1)
            notify_c1 = True
            links[c2].remove(c1)
        if not links[c2]: del links[c2]
    if notify_c2:
        bot.send_msg(c2, '%s: Disconnected from channel.'
            % channel.capitalisation.get(c1, c1_orig))
    if notify_c1:
        bot.send_msg(c1, '%s: Disconnected from channel.'
            % channel.capitalisation.get(c2, c2_orig))
    decay_links.discard(c1)
    decay_links.discard(c2)

# Mark an existing link so that it will eventually be removed
# if it is not refreshed by calling add_link().
def decay_link(bot, c1, c2):
    del_persistent_link(c1, c2)
    del_persistent_link(c2, c1)
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
    cchan = channel.capitalisation.get(chan.lower(), chan)
    if topic:
        bot.send_msg(lchan, '%s: Topic: %s' % (cchan, topic), no_link=True)
    for row in util.join_cols(*(names[i::9] for i in range(9))):
        bot.send_msg(lchan, '%s: Users: \2%s\2' % (cchan, row), no_link=True)

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
def h_add_chan_link(bot, id, chan, from_chan, full_msg):
    if not chan or not re.match(r'#\S*$', from_chan):
        message.reply(bot, id, chan, 'Error: invalid argument: "%s".' % from_chan)
    else:
        yield add_link(bot, from_chan, chan, True, True)

@link('!add-chan-link-from')
@auth.admin
def h_add_chan_link(bot, id, chan, from_chan, full_msg):
    if not chan or not re.match(r'#\S*$', from_chan):
        message.reply(bot, id, chan, 'Error: invalid argument: "%s".' % from_chan)
    else:
        yield add_link(bot, from_chan, chan, False, True)

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
        lnicks = yield channel.names(bot, lchan, include_prefix=False)
        if id.nick.lower() in map(str.lower, lnicks): continue
        bot.send_msg(lchan, msg, no_link=True)

@link('MESSAGE',  a=lambda bot, id, chan, msg:
                    (bot, id.nick, id, chan, msg))
@link('COMMAND',  a=lambda bot, id, chan, event, body, msg:
                    (bot, id.nick, id, chan, msg))
@link('SEND_MSG', a=lambda bot, chan, msg, kwds:
                    (bot, bot.nick, None, not kwds.get('no_link') and chan, msg))
def h_message(*args, **kwds):
    bot, nick, id, chan, msg = kwds['a'](*args)
    if not chan or chan.lower() not in links: return
    chan = channel.capitalisation.get(chan.lower(), chan)
    p_nick = channel.prefix_nick(bot, nick, chan)
    match = re.match(r'\x01ACTION (?P<act>.*?)\x01?$', msg)
    msg = '%s: * %s %s' % (chan, nick, match.group('act')) if match else \
          '%s: <%s> %s' % (chan, p_nick, msg)
    for lchan in links[chan.lower()]:
        bot.send_msg(lchan, msg, no_link=True)
        if id is not None:
            yield sign('PROXY_MSG', bot, id, lchan, msg, no_link=True)

@link('PROXY_MSG')
def h_proxy_msg(bot, id, chan, msg, no_link=False, **kwds):
    if no_link or chan.lower() not in links: return
    for lchan in links[chan.lower()]:
        yield sign('PROXY_MSG', bot, id, lchan, msg,
            **dict(kwds, no_link=True))

@link('TOPIC')
def h_topic(bot, source, chan, topic):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = source[0]
    msg = '%s: %s set topic to: %s' % (source, topic) if topic else \
          '%s: %s unset the topic.' % source
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)

@link('MODE')
def h_chan_mode(bot, source, chan, *args):
    if chan.lower() not in links: return
    if isinstance(source, tuple): source = source[0]
    chan = channel.capitalisation.get(chan.lower(), chan)
    msg = '%s: %s set mode: %s' % (chan, source, ' '.join(args))
    for lchan in links[chan.lower()]: bot.send_msg(lchan, msg, no_link=True)
