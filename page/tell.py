# Possible future changes:
#   - Require messages given upon joining a channel to be explicitly dismissed.
#   - Allow messages to be deleted with something like: <SENDER> !tell_cancel RECIPIENT.
#   - Allow each USER@HOST sender to leave at most 1 message for each RECIPIENT.
#   - Allow a USER@HOST sender to edit their last message to any RECIPIENT.
#   - Display only 3 messages at once, delivering further messages by PM.

from util import LinkSet
from auth import admin
from collections import namedtuple
from itertools import *
import pickle as pickle
import os.path
import datetime
import time
import re

link, install, uninstall = LinkSet().triple()

# The file where the plugin's persistent state is stored.
STATE_FILE = 'state/tell.pickle'

# Load the plugin's persistent state object.
def get_state():
    if not os.path.exists(STATE_FILE):
        return State()
    try:
        with open(STATE_FILE, 'r') as state_file:
            return pickle.load(state_file)
    except pickle.UnpicklingError:
        return State()
    except EOFError:
        return State()

# Save the plugin's persistent state object.
def put_state(state):
    with open(STATE_FILE, 'w') as state_file:
        pickler = pickle.Pickler(state_file)
        pickler.clear_memo()
        pickler.dump(state)

# The plugin's persistent state object.
class State(object):
    def __init__(self):
        self.msgs = []
    def __getinitargs__(self):
        return ()

# A saved message kept by the system.
Message = namedtuple('Message',
    ('time_sent', 'channel', 'from_id', 'to_nick', 'message'))

# Reply (in the same channel or by PM, as appropriate) to a message by `id'
# sent to `target' with the message `msg', possibly prefixing the message with
# their nick, unless `prefix' is given as False.
def reply(bot, id, target, msg, prefix=True):
    if prefix and target != None:
        msg = '%s: %s' % (id.nick, msg)
    bot.send_msg(target or id.nick, msg)


@link('COMMAND_LIST')
def list_tell(bot, reply):
    reply('tell NICK MESSAGE',
    'When NICK is next seen in this channel, MESSAGE will be delivered to them.'
    ' NICK is matched case-insensitively against the nick of anybody appearing'
    ' in the channel.')
    reply(None,
    'If NICK contains the characters * or ?, these will match any sequence of'
    ' of zero or more characters, or exactly 1 character, respectively.')
    reply(None,
    'If NICK contains any occurrence of ! or @, it will be matched against the'
    ' full NICK!USER@HOST of the recipient, instead of just their nick.')

@link('!tell')
def h_tell(bot, id, target, args, full_msg):
    if not target:
        reply(bot, id, target,
            'Error: the "tell" command may only be used in a channel.')
        return

    to_nick, msg = re.match(r'(\S+)\s+(.*)', args).groups()
    if to_nick.startswith('#'):
        reply(bot, id, target,
            'Error: "%s" is not a valid nick or hostmask.' % to_nick)
        return

    state = get_state()
    record = Message(
        time_sent   = datetime.datetime.utcnow(),
        channel     = target,
        from_id     = id,
        to_nick     = to_nick,
        message     = msg)
    state.msgs.append(record)
    put_state(state)
    reply(bot, id, target, 'Yes.')


@link('!tell_list')
@admin
def h_tell_list(bot, id, target, args, full_msg):
    output = lambda msg: reply(bot, id, target, msg, prefix=False)
    state = get_state()
    lines = [('From', 'To', 'Channel', 'Time', 'Message')]
    for msg in state.msgs:
        lines.append((
            '%s!%s@%s' % tuple(msg.from_id),
            msg.to_nick,
            msg.channel,
            msg.time_sent.strftime('%Y-%m-%d %H:%M'),
            msg.message))
    widths = reduce(
        lambda l, m: tuple(max(i, j) for (i, j) in izip(l, m)),
        (map(len, l) for l in lines))
    for line in lines:
        line = tuple(s+' '*(w-len(s)) for (s, w) in izip(line, widths))
        output('  '.join(line).strip())
    output('End of tell_list')


@link('!tell_reset')
@admin
def h_tell_reset(bot, id, target, args, full_msg):
    put_state(State())
    reply(bot, id, target, 'Done.')

'''
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    report(bot, id, chan)
'''

@link('MESSAGE')
def h_message(bot, id, target, msg):
    if target: report(bot, id, target)

# Handle an action by `id' on `chan', possibly resulting in `id' being notified
# of messages left for them.
def report(bot, id, chan):
    state = get_state()
    state.msgs = list(ifilterfalse(
        lambda m: report_msg(bot, id, chan, m), state.msgs))
    put_state(state)

# Handles an action by `id' on `chan' in the context of the Message instance
# `msg', possibly notifying `id' of this message, in which case returns True;
# otherwise returns False.
def report_msg(bot, id, chan, msg):
    if msg.channel != chan: return False
    if not msg_matches_id(msg, id): return False
    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False
    d_mins, d_secs = divmod(delta.seconds, 60)
    d_hours, d_mins = divmod(d_mins, 60)
    bot.send_msg(chan, '%s: %s said on %s UTC (%s ago):' % (
        id.nick,
        '%s!%s@%s' % tuple(msg.from_id),
        msg.time_sent.strftime('%d %b %Y, %H:%M'),
        '%sd, %02d:%02d:%02d' % (delta.days, d_hours, d_mins, d_secs)))
    bot.send_msg(chan, "<%s> %s" % (msg.from_id.nick, msg.message))
    return True

# Returns True if the given message matches the given user ID as a recipient,
# or otherwise returns False.
def msg_matches_id(msg, id):
    str = '%s!%s@%s' % tuple(id) if re.search(r'!|@', msg.to_nick) else id.nick
    pat = wc_to_re(msg.to_nick)
    print 'DEBUG: str=%s; pat=%s' % (str, pat)
    return re.match(pat, str, re.I) != None

# Returns a Python regular expression pattern string equivalent to the given
# wildcard pattern (which accepts only the entire input, not part of it).
def wc_to_re(wc):
    def sub(match):
        if match.group(1): return '.*'
        elif match.group(2): return '.'
        else: return re.escape(match.group(3))
    return '^' + re.sub(r'(\*)|(\?)|([^*?]+)', sub, wc) + '$'
