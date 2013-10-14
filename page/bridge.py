import re

from untwisted.magic import sign

import util
import channel
import message

link, install, uninstall = util.LinkSet().triple()  


bridges = util.read_list('conf/bridge.py')


@link('IRC')
@link('MINECRAFT')
@link('TERRARIA')
def h_msg(bot, source, msg, source_name=None):
    for source, target in targets(source):
        name = source_name or source
        yield sign('BRIDGE', bot, target, '%s: %s' % (name, msg))

def notice(bot, source, head, *args, **kwds):
    include_self = kwds.get('include_self', True)
    for source, target in targets(source, include_self=include_self):
        bot.drive(('BRIDGE', head), bot, target, *args)

def targets(source_chan, include_self=False):
    for bridge in bridges:
        sources = [c for c in bridge if c.lower() == source_chan.lower()]
        if not sources: continue
        for target in bridge:
            if target.lower() != source_chan.lower() or include_self:
                yield (sources[0], target)


@link(('BRIDGE', 'NAMES_RES'))
def h_bridge_names_res(bot, target, target_, source_name, names):
    if target.lower() != target_.lower(): return
    msg = 'Online in %s: %s.' % (source_name, ', '.join(names))
    yield sign('BRIDGE', bot, target, msg)

@link(('BRIDGE', 'NAMES_ERR'))
def h_bridge_names_err(bot, target, target_, source_name, error):
    if target.lower() != target_.lower(): return
    msg = 'Failed to enumerate users in %s: %s.' % (source_name, error)
    yield sign('BRIDGE', bot, target, msg)


@link('BRIDGE')
def h_bridge(bot, target_chan, msg):
    if not target_chan.startswith('#'): return
    bot.send_msg(target_chan, msg)


@link('HELP')
def h_help_online_short(bot, reply, args):
    reply('online [LOCATION]',
    'Lists online users in connected game worlds and IRC channels.')

@link(('HELP', 'online'))
def h_help_online(bot, reply, args):
    reply('online [MINECRAFT_WORLD | +TERRARIA_WORLD | #IRC_CHANNEL]',
    'Lists the online users in the specified game world or IRC channel,'
    ' or if none is specified, lists the users in all connected locations.',
    'May be used from within a game or from IRC, but must be used from a '
    ' distinct location that is linked by relay to the target location.')

@link('!online')
def h_online(bot, id, chan, args, full_msg):
    if chan is None: return message.reply(bot, id, chan,
        'The "online" command may not be used by PM.')
    notice(bot, chan, 'NAMES_REQ', chan, args)

@link(('BRIDGE', 'NAMES_REQ'))
def h_bridge_names_req(bot, target, source, query):
    if not target.startswith('#'): return
    if query and query.lower() != target.lower(): return
    names = yield channel.names(bot, target)
    names = channel.strip_names(names)
    notice(bot, target, 'NAMES_RES', source, target, names)


@link('MESSAGE')
def h_message(bot, id, chan, msg):
    if chan is None: return
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
    cmsg = '%s left the channel%s.' % \
        (id.nick, (' (%s)' % msg) if msg else '')
    yield sign('IRC', bot, chan, cmsg)

@link('OTHER_KICKED')
def h_other_kick(bot, other_nick, op_id, chan, msg):
    cmsg = '%s was kicked by %s%s.' % \
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
