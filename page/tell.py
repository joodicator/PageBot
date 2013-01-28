# Possible future changes:
#   - Require messages given upon joining a channel to be explicitly dismissed.
#     OR only notify users of the presence of messages, requiring them to
#     retrieve their messages manually.
#   - Display only 3 messages at once, delivering further messages by PM.
#   - Allow each USER@HOST sender to leave at most 1 message for each RECIPIENT.
#   - Allow a USER@HOST sender to edit or delete their last message to any RECIPIENT.

from util import LinkSet
import util
from auth import admin
from message import reply

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

# The memory-cached persisten global state.
STATE = None

# Load the plugin's persistent state object.
def get_state():
    # We use the in-memory state if it exists, to avoid excessive file IO.
    global STATE
    if STATE: return STATE
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as state_file:
                STATE = pickle.load(state_file)
        except pickle.UnpicklingError: pass
        except EOFError: pass
    if not STATE: STATE = State()
    return STATE

# Save the plugin's persistent state object.
def put_state(state):
    global STATE
    STATE = state

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

@link('HELP')
def h_help_tell_short(bot, reply, args):
    reply('tell NICK MESSAGE',
    'When NICK is next seen in this channel, MESSAGE will be delivered to them.')

@link(('HELP', 'tell'))
def h_help_tell(bot, reply, args):
    h_help(bot, reply, args)
    reply('',
    'NICK is matched case-insensitively against the nick of anybody appearing'
    ' in the channel.')
    reply('',
    'If NICK contains the characters * or ?, these will match any sequence of'
    ' of zero or more characters, or exactly 1 character, respectively.')
    reply('',
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
    reply(bot, id, target, 'It shall be done.')

@link('HELP')
def h_help_untell_short(bot, reply, args):
    reply('untell NICK',
    'Cancels a message left using "tell".')

@link(('HELP', 'untell'))
def h_help_untell(bot, reply, args):
    reply('untell NICK',
    'Cancels all undelivered messages issued using the "tell" command'
    ' with the same NICK, by any user with your hostmask.')

@link('!untell')
def h_untell(bot, id, target, args, full_msg):
    if not target:
        return reply(bot, id, target,
        'Error: the "untell" command may only be used in a channel.')
    state = get_state()
    def will_cancel(msg):
        if msg.channel != target: return False
        if msg.to_nick != args: return False
        if msg.from_id != id: return False
        return True
    msgs = [(will_cancel(m), m) for m in state.msgs]
    msgs_cancel = [m for (b, m) in msgs if b]
    msgs_keep = [m for (b, m) in msgs if not b]
    if not msgs_cancel:
        return reply(bot, id, target,
        'There were no messages to "%s" from %s in %s.'
        % (args, '%s@%s!%s' % tuple(id), target))
    state.msgs = msgs_keep
    count = len(msgs_cancel)
    put_state(state)
    reply(bot, id, target, '%s %s deleted.' %
        (count, 'message' if count == 1 else 'messages'))


@link('!tell_list')
@admin
def h_tell_list(bot, id, target, args, full_msg):
    output = lambda msg: reply(bot, id, target, msg, prefix=False)
    state = get_state()
    lines = [('#', 'From', 'To', 'Channel', 'Time', 'Message')]
    for (num, msg) in izip(count(1), state.msgs):
        lines.append((
            str(num),
            '%s!%s@%s' % tuple(msg.from_id),
            msg.to_nick,
            msg.channel,
            msg.time_sent.strftime('%Y-%m-%d %H:%M'),
            msg.message))
    lines = util.align_table(lines)
    output('\2' + lines[0])
    map(output, lines[1:])
    output('\2End of tell_list')

@link('!tell_reset')
@admin
def h_tell_reset(bot, id, target, args, full_msg):
    put_state(State())
    reply(bot, id, target, 'Done.')

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    notify_msgs(bot, id, chan)

@link('MESSAGE')
def h_message(bot, id, target, msg):
    if target: deliver_msgs(bot, id, target)

# Notify `id' of messages left for them in `chan', if any.
def notify_msgs(bot, id, chan):
    state = get_state()
    msgs = filter(lambda m: would_deliver(id, chan, m), state.msgs)
    if len(msgs) > 1:
        reply(bot, id, chan,
            'You have %s messages; say anything to read them.' % len(msgs))
    elif len(msgs):
        reply(bot, id, chan,
            'You have a message; say anything to read it.')

# Deliver to `id' any messages left for them in `chan'.
def deliver_msgs(bot, id, chan):
    state = get_state()
    msgs = [(would_deliver(id, chan, m), m) for m in state.msgs]
    msgs_deliver = [m for (b, m) in msgs if b]
    msgs_keep = [m for (b, m) in msgs if not b]
    if not msgs_deliver: return
    for msg in msgs_deliver:
        deliver_msg(bot, id, chan, msg)
    state.msgs = msgs_keep
    put_state(state)

# Unconditionally deliver `msg' to `id' in `chan'.
def deliver_msg(bot, id, chan, msg):
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

# Returns True if `msg' would be delivered at this time to `id' in `chan',
# or otherwise returns False.
def would_deliver(id, chan, msg):
    if msg.channel != chan: return False
    
    str = '%s!%s@%s' % tuple(id) if re.search(r'!|@', msg.to_nick) else id.nick
    pat = wc_to_re(msg.to_nick)
    if re.match(pat, str, re.I) == None: return False

    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False    
    
    return True

# Returns a Python regular expression pattern string equivalent to the given
# wildcard pattern (which accepts only the entire input, not part of it).
def wc_to_re(wc):
    def sub(match):
        if match.group(1): return '.*'
        elif match.group(2): return '.'
        else: return re.escape(match.group(3))
    return '^' + re.sub(r'(\*)|(\?)|([^*?]+)', sub, wc) + '$'
