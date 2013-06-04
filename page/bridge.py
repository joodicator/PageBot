from untwisted.magic import sign
import util
import re

link, install, uninstall = util.LinkSet().triple()  


bridges = util.read_list('conf/bridge.py')


@link('IRC')
@link('MINECRAFT')
@link('TERRARIA')
def h_msg(bot, source_chan, msg):
    for bridge in bridges:
        sources = [c for c in bridge if c.lower() == source_chan.lower()]
        if not sources: continue
        targets = (c for c in bridge if c.lower() != source_chan.lower())
        for target in targets:
            yield sign('BRIDGE', bot, target, '%s: %s' % (sources[0], msg))


@link('BRIDGE')
def h_bridge(bot, target_chan, msg):
    if not target_chan.startswith('#'): return
    bot.send_msg(target_chan, msg)


@link('MESSAGE')
def h_message(bot, id, chan, msg):
    match = re.match(r'\x01ACTION (?P<msg>.*)', msg)
    if match:
        if match.group('msg').startswith('!'): return
        cmsg = '* %s %s' % (id.nick, match.group('msg'))
    else:
        if msg.startswith('!'): return
        cmsg = '<%s> %s' % (id.nick, msg)
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    cmsg = '%s joined the channel.' % id.nick
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_PART')
def h_other_part(bot, id, chan, msg):
    cmsg = '%s left the channel' % \
        (id.nick, (' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_KICKED')
def h_other_kick(bot, other_nick, op_id, chan, msg):
    cmsg = '%s was kicked by %s' % \
        (other_nick, op_id.nick, (' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_QUIT_CHAN')
def h_other_quit(bot, id, chan, msg):
    cmsg = '%s quit the network%s.' % \
        (id.nick, (' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_NICK_CHAN')
def h_other_nick(bot, id, new_nick, chan):
    cmsg = '%s is now known as %s.' % (id.nick, new_nick)
    yield sign('IRC', bot, chan, cmsg)

@link('SELF_JOIN')
def h_self_join(bot, chan):
    cmsg = 'Joined the channel.'
    yield sign('IRC', bot, chan, cmsg)

@link('SELF_PART')
def h_self_part(bot, chan, msg):
    cmsg = 'Left the channel%s.' % ((' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('SELF_KICKED')
def h_self_kicked(bot, chan, op_id, msg):
    cmsg = 'Kicked from the channel by %s%s.' % \
        (op_id.nick, (' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('CLOSING_CHAN')
def h_self_quit(bot, chan):
    cmsg = 'Disconnected from the network.'
    yield sign('IRC', bot, chan, cmsg)
