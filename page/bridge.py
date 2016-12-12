from datetime import datetime
from itertools import *
import re

from untwisted.magic import sign

import util
import channel
import message

link, install, uninstall = util.LinkSet().triple()

bridges = util.read_list('conf/bridge.py', default=True)
substitutions = util.read_list('conf/substitute.py', default=True)


@link('IRC')
@link('MINECRAFT')
@link('TERRARIA')
def h_msg(bot, source, msg, source_name=None):
    if source is None:
        return
    if type(msg) is unicode:
        msg = msg.encode('utf8')
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

@link(('BRIDGE', 'MESSAGE'), action=False)
@link(('BRIDGE', 'ACTION'),  action=True)
def h_bridge_message(bot, name, target, msg, reply, action):
    match = re.match(r'(?P<cmd>!\S+)\s*(?P<args>.*)', msg)
    if not match: return
    event = ('BRIDGE', 'ACTION', match.group('cmd')) if action else \
            ('BRIDGE',           match.group('cmd'))
    yield sign(event, bot, name, target, match.group('args'), reply)


@link(('BRIDGE', 'HELP'), ('BRIDGE', 'HELP', 'time'))
def h_help_date_short(bot, reply, args):
    reply('time',
    'Displays the current time in UTC.')

@link(('BRIDGE','!time'), ('BRIDGE','!date'))
def h_date_time(bot, name, target, args, reply):
    reply(
        datetime.utcnow().strftime('%H:%M:%S %a %d/%b/%Y UTC'),
        prefix = False,
        no_bridge = True)


@link('HELP', ('BRIDGE', 'HELP'))
def h_help_online_short(bot, reply, args):
    reply('online [LOCATION]',
    'Lists online users in connected game worlds and IRC channels.')

@link(('HELP', 'online'), ('BRIDGE', 'HELP', 'online'))
def h_help_online(bot, reply, args):
    reply('online [MINECRAFT_WORLD | +TERRARIA_WORLD | #IRC_CHANNEL]',
    'Lists the online users in the specified game world or IRC channel,'
    ' or if none is specified, lists the users in all connected locations.',
    'May be used from within a game or from IRC, but must be used from a '
    ' distinct location that is linked by relay to the target location.')

@link(('SIMPLE', '!online'), ('BRIDGE', '!online'))
def h_online(bot, name, target, args, reply):
    if target is None: return
    include_self = not target.startswith('#')
    notice(bot, target, 'NAMES_REQ', target, args, include_self=include_self)
    reply(no_bridge=True)


@link(('BRIDGE', 'NAMES_RES'))
def h_bridge_names_res(bot, target, target_, source_name, names):
    if target.lower() != target_.lower() and target_ != '*':
        return
    msg = 'Online in %s: %s.' % (
        source_name, ', '.join(sorted(names)) if names else '(nobody)')
    yield sign('BRIDGE', bot, target, msg)

@link(('BRIDGE', 'NAMES_ERR'))
def h_bridge_names_err(bot, target, target_, source_name, error):
    if target.lower() != target_.lower(): return
    msg = 'Failed to enumerate users in %s: %s' % (source_name, error)
    yield sign('BRIDGE', bot, target, msg)


@link('BRIDGE')
def h_bridge(bot, target_chan, msg):
    if not target_chan.startswith('#'): return
    bot.send_msg(target_chan, msg, no_bridge=True)
    if isinstance(msg, unicode): msg = msg.encode('utf-8')
    yield sign('PROXY_MSG', bot, None, target_chan, msg)

@link(('BRIDGE', 'NAMES_REQ'))
def h_bridge_names_req(bot, target, source, query):
    if not target.startswith('#'): return
    if query and query.lower() != target.lower(): return
    names = channel.track_channels[target.lower()]
    notice(bot, target, 'NAMES_RES', source, target, names)


@link('MESSAGE',  a=lambda bot, id, chan, msg:
                    (bot, id.nick, chan, msg))
@link('SEND_MSG', a=lambda bot, chan, msg, kwds:
                    (bot, bot.nick, chan if not kwds.get('no_bridge') else None, msg))
def h_message(*args, **kwds):
    bot, nick, chan, msg = kwds['a'](*args)
    if chan is None: return
    match = re.match(r'\x01ACTION (?P<msg>.*)', msg)
    if match:
        cmsg = '* %s %s' % (nick, match.group('msg'))
    else:
        cmsg = '<%s> %s' % (nick, msg)
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
def h_other_quit(bot, id, msg, chan):
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

@link('TOPIC')
def h_topic(bot, source, chan, topic):
    if isinstance(source, tuple): source = source[0]
    cmsg = '%s set topic to: %s' % (source, topic) if topic else \
           '%s unset the topic.' % source
    yield sign('IRC', bot, chan, cmsg)

@link('MODE')
def h_mode(bot, source, chan, *modes):
    if isinstance(source, tuple): source = source[0]
    cmsg = '%s set mode: %s' % (source, ' '.join(modes))
    yield sign('IRC', bot, chan, cmsg)


#===============================================================================
def substitute_reply(context, local_name, msg_local, msg_bridge, cancel_bridge):
    def reply(rmsg=None, from_name=None, prefix=True, no_bridge=False):
        if from_name is None and rmsg is not None:
            from_name = lambda name: rmsg
        if from_name:
            if prefix:
                _from_name = from_name
                from_name = lambda name: '%s: %s' % (name, _from_name(name))
            msg_local(from_name(local_name))
            if not no_bridge:
                msg_bridge(from_name(substitute_name(context, local_name)))
        if no_bridge:
            cancel_bridge()
    return reply

# Apply any appropriate substitutions to the r'\b'-separated words in `text'.
def substitute_text(context, text):
    context = context.lower()
    for r_context, find, repl in substitutions:
        if r_context.lower() == context:
            text = re.sub(
                r'\b(%s)\b' % re.escape(find),
                lambda match: _substitute_name(match.group(), find, repl),
                text, flags=re.I)
    return text

# Apply any appropriate substitutions that wholly match `name'.
def substitute_name(context, name):
    context = context.lower()
    for r_context, find, repl in substitutions:
        if r_context.lower() == context and find.lower() == name.lower():
            name = _substitute_name(name, find, repl)
    return name

# Apply to `repl' any changes in capitalisation from `find' to `name'.
def _substitute_name(name, find, repl):
    def iter():
        identity = lambda x: x
        trans = identity
        for name_chr, find_chr, repl_chr in izip(name, find, repl):
            trans = str.lower if find_chr.isupper() and name_chr.islower() else \
                    str.upper if find_chr.islower() and name_chr.isupper() else \
                    identity
            yield trans(repl_chr)
        yield trans(repl[min(len(find), len(name)):])
    return ''.join(iter())

