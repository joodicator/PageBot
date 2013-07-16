#==============================================================================#
# tell.py - provides !tell, and related commands, to allow users to leave each
# other messages in an IRC channel.

import util
import auth
from util import LinkSet
from auth import admin
from message import reply
import channel
import untwisted.magic

from collections import namedtuple
from itertools import *
import pickle as pickle
import os.path
import datetime
import time
import re

#==============================================================================#
link, install, uninstall = LinkSet().triple()

# The number of days from a message's timestamp after which it may be deleted
# from the dismissed_msgs list.
DISMISS_DAYS = 30

# The file where the plugin's persistent state is stored.
STATE_FILE = 'state/tell.pickle'

# The memory-cached persistent global state.
STATE = None

# A saved message kept by the system.
Message = namedtuple('Message',
    ('time_sent', 'channel', 'from_id', 'to_nick', 'message'))

# The plugin's persistent state object.
class State(object):
    def __init__(self):
        self.msgs = []
        self.dismissed_msgs = []
    def __getinitargs__(self):
        return ()

#==============================================================================#
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

#==============================================================================#
@link('HELP')
def h_help_tell_short(bot, reply, args):
    reply('tell NICK MESSAGE',
    'When NICK is next seen in this channel, MESSAGE will be delivered to them.')

@link(('HELP', 'tell'))
def h_help_tell(bot, reply, args):
    h_help_tell_short(bot, reply, args)
    reply('',
    'If NICK contains any occurrence of ! or @, it will be matched against'
    ' the full NICK!USER@HOST of the recipient, instead of just their nick;'
    ' if NICK contains the wildcard characters * or ?, these will match any'
    ' sequence of 0 or more characters, or exactly 1 character, respectively.')

@link('!tell')
def h_tell(bot, id, target, args, full_msg):
    # Secretly, admins may prepend the arguments with the target channel.
    match = re.match(r'(#\S+)\s+(.*)', args)
    if match:
        is_admin = yield auth.check(bot, id)
        if is_admin:
            channel, args = match.groups()
        else:
            reply(bot, id, target,
            'Error: "%s" is not a valid nick or hostmask.' % match.group(1))
            return
    elif target:
        channel = target
    else:
        reply(bot, id, target,
        'Error: the "tell" command may only be used in a channel.')
        return

    to_nick, msg = re.match(r'(\S+)\s+(.*)', args).groups()

    state = get_state()
    record = Message(
        time_sent   = datetime.datetime.utcnow(),
        channel     = channel,
        from_id     = id,
        to_nick     = to_nick,
        message     = msg)
    state.msgs.append(record)
    put_state(state)
    reply(bot, id, target, 'It shall be done.')

#==============================================================================#
@link('HELP')
def h_help_untell_short(bot, reply, args):
    reply('untell NICK',
    'Cancels messages left using "tell".')

@link(('HELP', 'untell'))
def h_help_untell(bot, reply, args):
    reply('untell NICK',
    'Cancels all undelivered messages issued using the "tell" command'
    ' with the same NICK, by any user with your hostmask.')

@link('!untell')
def h_untell(bot, id, target, args, full_msg):
    # Secrely, arguments may prepend the arguments with the target channel.
    match = re.match(r'(#\S+)\s+(.*)', args)
    if match:
        is_admin = yield auth.check(bot, id)
        if is_admin:
            channel, args = match.groups()
        else:
            reply(bot, id, target,
            'Error: "%s" is not a valid nick or hostmask.' % match.group(1))
            return
    elif target:
        channel = target
    else:
        reply(bot, id, target,
        'Error: the "untell" command may only be used in a channel.')
        return

    def will_cancel(msg):
        if msg.channel != channel: return False
        if msg.to_nick != args: return False
        if msg.from_id != id: return False
        return True

    state = get_state()
    msgs = [(will_cancel(m), m) for m in state.msgs]
    msgs_cancel = [m for (b, m) in msgs if b]
    msgs_keep = [m for (b, m) in msgs if not b]
    if not msgs_cancel:
        reply(bot, id, target,
            'There were no messages to "%s" from %s in %s.'
            % (args, '%s!%s@%s' % tuple(id), channel))
        return
    state.msgs = msgs_keep
    count = len(msgs_cancel)
    put_state(state)
    reply(bot, id, target, '%s %s deleted.' %
        (count, 'message' if count == 1 else 'messages'))

#==============================================================================#
@link('HELP')
def h_help_dismiss_short(bot, reply, args):
    reply('dismiss [NICK]',
    'Cancels delivery of the last message left for you.')

@link(('HELP', 'dismiss'))
def h_help_dismiss(bot, reply, args):
    reply('dismiss [NICK]',
    'If NICK is given, dismisses the most recent message left for you by NICK,'
    ' preventing it from being delivered; otherwise, dismisses the most recent'
    ' message left by anybody. Messages may be recovered using "undismiss".',
    'NICK may be an IRC nick or a NICK!USER@HOST, and may contain the wildcard'
    ' characters * and ?, as specified in "help tell", in which case the last'
    ' matching message is dismissed.')

@link('!dismiss')
def h_dismiss(bot, id, target, query, *args):
    state = get_state()
    msgs = [m for m in state.msgs if not query or match_id(query, m.from_id)]
    if not msgs: return reply(bot, id, target,
        'You have no messages%s to dismiss.' % (query and ' from "%s"' % query))
    msg = msgs[-1]
    state.msgs.remove(msg)
    state.dismissed_msgs = [m for m in state.dismissed_msgs
        if (datetime.datetime.utcnow() - m.time_sent).days <= DISMISS_DAYS]
    state.dismissed_msgs.append(msg)
    put_state(state)
    count = len(state.msgs)
    reply(bot, id, target,
        '1 message from %s deleted; you now have %s message%s'
        ' (you may reverse this using "undismiss").'
        % (msg.from_id.nick, count, 's' if count != 1 else ''))

#==============================================================================#
@link('HELP')
def h_help_undismiss_short(bot, reply, args):
    reply('undismiss [NICK]',
    'Restores the last message that you dismissed.')

@link(('HELP', 'undismiss'))
def h_help_undismiss(bot, reply, args):
    reply('undismiss [NICK]',
    'Reverses the effect of "dismiss", restoring the last dismissed message'
    ' from NICK, or from anybody if NICK is not specified. This may be done'
    ' multiple times to restore messages from up to %s days ago.'
    % DISMISS_DAYS,
    'As with "dismiss", NICK may take the form NICK!USER@HOST, and may contain'
    ' the wildcard characters * and ?.')

@link('!undismiss')
def h_undismiss(bot, id, target, query, *args):
    state = get_state()
    msgs = [m for m in state.dismissed_msgs
        if not query or match_id(query, m.from_id)]
    if not msgs: return reply(bot, id, target,
        'You have no dismissed messages%s.'
        % (query and ' from "%s"' % query))
    msg = msgs[-1]
    state.dismissed_msgs.remove(msg)
    state.msgs.append(msg)
    put_state(state)
    count = len(state.msgs)
    reply(bot, id, target,
        '1 message from %s restored; you now have %s message%s'
        ' (say anything to read %s).'
        % (msg.from_id.nick, count, 's' if count != 1 else '',
        'them' if count != 1 else 'it'))

#==============================================================================#
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

#==============================================================================#
@link('!tell_reset')
@admin
def h_tell_reset(bot, id, target, args, full_msg):
    put_state(State())
    reply(bot, id, target, 'Done.')

#==============================================================================#
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    notify_msgs(bot, id, chan)

@link('MESSAGE')
def h_message(bot, id, target, msg):
    if target: deliver_msgs(bot, id, target)

@link('OTHER_NICK_CHAN')
def h_nick(bot, id, new_nick, chan):
    state = get_state()
    old_id = util.ID(*id)
    new_id = util.ID(new_nick, old_id.user, old_id.host)
    new_msgs = {m for m in state.msgs
                if would_deliver(new_id, chan, m)
                and not would_deliver(old_id, chan, m)}
    if new_msgs: notify_msgs(bot, new_id, chan)

#==============================================================================#
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

#==============================================================================#
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

#==============================================================================#
# Unconditionally deliver `msg' to `id' in `chan', or by PM if `chan' is None.
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

#==============================================================================#
# Returns True if `msg' would be delivered at this time to `id' in `chan',
# or otherwise returns False.
def would_deliver(id, chan, msg):
    if msg.channel != chan: return False
    if not match_id(msg.to_nick, id): return False
    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False    
    return True

#==============================================================================#
# Returns True if `query', which is is a wildcard expression matching either a
# nick or a nick!user@host, matches the given id.
def match_id(query, id):
    id_str = '%s!%s@%s' % tuple(id) if re.search(r'!|@', query) else id.nick
    return re.match(wc_to_re(query), id_str, re.I) is not None

#==============================================================================#
# Returns a Python regular expression pattern string equivalent to the given
# wildcard pattern (which accepts only the entire input, not part of it).
def wc_to_re(wc):
    def sub(match):
        if match.group(1): return '.*'
        elif match.group(2): return '.'
        else: return re.escape(match.group(3))
    return '^' + re.sub(r'(\*)|(\?)|([^*?]+)', sub, wc) + '$'
