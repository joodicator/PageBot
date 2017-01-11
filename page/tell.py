#==============================================================================#
# tell.py - provides !tell, and related commands, to allow users to leave each
# other messages in an IRC channel.

from collections import namedtuple
from collections import Counter
from copy import deepcopy
from itertools import *
import pickle as pickle
import traceback
import os.path
import datetime
import time
import re

from untwisted.magic import sign

from message import reply
from util import multi, wc_to_re
from auth import admin
import runtime
import channel
import util
import auth


#==============================================================================#
link, install, uninstall = util.LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'auth')

#==============================================================================#
# Memory-cached plugin state.
current_state = None


# File where the plugin state is stored.
STATE_FILE = 'state/tell.pickle'

# After this many days, dismissed messages may be deleted.
DISMISS_DAYS = 30

# Date format used by !tell? and !tell+.
DATE_FORMAT_SHORT = '%Y-%m-%d %H:%M'

# Maximum number of history states to remember.
HISTORY_SIZE = 8 

# No interval of time shorter than this shall pass between repeated
# notification of new messages when the recipient is changing their nick.
MIN_NICKCHANGE_NOTIFY_INTERVAL_S = 3600 # 1 hour

# The maximum number of messages that may be sent by each user,
# where users are identified according to same_sender().
MAX_SENT = 12

# The maximum number of messages that may be sent from any given user
# to a single recipient (given by a wildcard expression).
MAX_SENT_WC = 3

# The maximum number of messages that may be sent from any given user
# where the recipient is given as a regular expression.
MAX_SENT_RE = 4

# The most messages that will be automatically delivered in a channel.
# When exceeded, the recipient will be instructed to read by PM using !read.
MAX_DELIVER_CHAN = 4

# The most messages that will be delivered at once by PM when using !read.
# When exceeded, the recipient will be prompted to enter !read again.
MAX_DELIVER_PM = 4

#-------------------------------------------------------------------------------
# A saved message kept by the system.
Message = namedtuple('Message',
    ('time_sent', 'channel', 'from_id', 'to_nick', 'message'))
Message.__getstate__ = lambda *a, **k: None

#-------------------------------------------------------------------------------
# The plugin's persistent state object.
class State(object):
    def __init__(self):
        # All undelivered messages, in order sent.
        self.msgs = []

        # All dismissed messages, in order dismissed.
        self.dismissed_msgs = []

        # The most recent time, if any, when each message's receipient was
        # notified of its existence.
        self.last_notify = dict() 

        self.prev_state = None
        self.next_state = None        

    def __setstate__(self, new_dict):
        self.__init__()
        self.__dict__.update(new_dict)

#==============================================================================#
# Retrieve a copy of the plugin's state.
def get_state():
    return deepcopy(load_state())

# Commit a forward change to the plugin's state.
def put_state(state):
    current_state.next_state = state
    state.prev_state = current_state
    state.next_state = None

    # Prune undo history based on HISTORY_SIZE.
    old_state = state
    for count in range(HISTORY_SIZE):
        if old_state.prev_state is None: break
        old_state = old_state.prev_state
    else:
        old_state.prev_state = None

    set_state(state)

# Retrieve the plugin's state.
def load_state():
    global current_state
    if not current_state and os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as state_file:
                current_state = pickle.load(state_file)
        except pickle.UnpicklingError: pass
        except EOFError: pass    
    if not current_state:
        current_state = State()
    return current_state

# Change to the given state without any processing of metadata.
def set_state(state):
    global current_state
    with open(STATE_FILE, 'w') as state_file:
        pickler = pickle.Pickler(state_file)
        pickler.clear_memo()
        pickler.dump(state)
    current_state = state    

class HistoryEmpty(Exception): pass

# Restores the state which existed before the last call to put_state().
# Raises HistoryEmpty if no such state exists.
def undo_state():
    state = load_state().prev_state
    if state is None: raise HistoryEmpty
    set_state(state)

# Restores the state which existed before the last call to undo_state().
# Raises HistoryEmpty if no such state exists.
def redo_state():
    state = load_state().next_state
    if state is None: raise HistoryEmpty
    set_state(state)

# Mark that msg's recipient has presently been notified of it.
def set_last_notify(msg, state):
    state.last_notify[msg] = time.time()
    for other_msg in state.last_notify.keys():
        if other_msg not in state.msgs:
            state.last_notify.pop(other_msg, None)

#==============================================================================#
@link('HELP*')
def h_help_tell_short(bot, reply, args):
    reply('tell NICK MESSAGE',
    'When NICK is next seen in this channel, MESSAGE will be delivered to them.')

@link(('HELP', 'tell'), ('HELP', 'page'))
def h_help_tell(bot, reply, args):
    if args and int(args) == 2:
        reply('tell NICK MESSAGE\2 or \2tell NICK[, NICK[, ...]]: MESSAGE',
        'Leaves a message for the given NICK, or for each of the listed NICKs,'
        ' so that it will be delivered to them when next seen in this channel.'
        ' \2!page\2 may be used as a synonym for \2!tell\2.',
        'If NICK contains any occurrence of ! or @, it will be matched against'
        ' the full NICK!USER@HOST of the recipient instead of just their nick.'
        ' If NICK contains the wildcard characters * or ?, these will match any'
        ' sequence of 0 or more characters, or exactly 1 character,'
        ' respectively.',
        'Additionally, NICK may consist of multiple alternatives separated by'
        ' the forward slash character (/), in which case the message will be'
        ' delivered to the first of these recipients that is seen.')
    else:
        reply('tell NICK MESSAGE',
        'Leaves a message for NICK so that it will be delivered to them when'
        ' next seen in this channel. Example: "!tell alice Hello.". For'
        ' advanced features, see \2!help tell 2\2. See also: \2!help untell\2'
        ' and \2!help dismiss\2.')

#-------------------------------------------------------------------------------
@link('!tell', '!page')
def h_tell(bot, id, target, args, full_msg):
    # Secretly, admins may prepend the arguments with the target channel.
    match = re.match(r'(#\S+)\s+(.*)', args)
    if match:
        is_admin = yield auth.check(bot, id)
        if is_admin: channel, args = match.groups()
    elif target:
        channel = target
    else:
        reply(bot, id, target,
            'Error: the "tell" command may only be used in a channel.')
        return

    match = re.match(r'(%(nick)s(?:(?:\s*,\s*%(nick)s)*\s*:)?)\s+(.*)'
        % {'nick': r'[^\s,]*[^\s,:]'}, args)
    if not match:
        reply(bot, id, target,
            'Error: invalid syntax. See "help tell" for correct usage.')
        return

    to, msg = match.groups()
    to_nicks = [nick.strip() for nick in to.strip(':').split(',')]
    sent_msgs = []
    state = get_state()
    for to_nick in to_nicks:
        if re.search(r'[#]', to_nick):
            reply(bot, id, target,
                'Error: "%s" is not a valid IRC nick or hostmask'
                ' (no messages sent).' % to_nick)
            return

        record = Message(
            time_sent   = datetime.datetime.utcnow(),
            channel     = channel,
            from_id     = id,
            to_nick     = to_nick,
            message     = msg)
        state.msgs.append(record)
        sent_msgs.append(record)

    sent_count = len(to_nicks)
    same_sent = [m for m in state.msgs if same_sender(m.from_id, id)
                 and m.channel.lower() == channel.lower()]
    if len(same_sent) > MAX_SENT:
        reply(bot, id, target,
            'Error: you may leave no more than %d messages at once.' % MAX_SENT)
        return
    if '$' in to_nick:
        reply(bot, id, target,
            'Error: the recipient may not contain "$". Note that regular expressions'
            ' are no longer supported.')
        return
    else:
        for recv in (p for n in to_nicks for p in n.split('/')):
            norm_recv = lambda r: re.sub(r'\*+', r'*', r).lower()
            same_recv = [m for m in same_sent if norm_recv(recv) in
                         map(norm_recv, m.to_nick.split('/'))]       
            if len(same_recv) > MAX_SENT_WC:
                reply(bot, id, target,
                    'Error: you may leave no more than %d messages for "%s"'
                    ' at once.' % (MAX_SENT_WC, recv))
                return

    put_state(state)
    yield sign('TELL_SENT', bot, id, target, sent_msgs)

@link('TELL_SENT')
def h_tell_sent(bot, id, target, sent_msgs, reply_msg=None):
    if reply_msg is None:
        reply_msg = 'It shall be done'
    if len(sent_msgs) > 1: reply(bot, id, target,
        '%s (%s messages sent).' % (reply_msg, len(sent_msgs)))
    else: reply(bot, id, target,
        '%s (1 message sent to "%s").' % (reply_msg, sent_msgs[0].to_nick))

#==============================================================================#
@link(('HELP', 'untell'), ('HELP', 'unpage'))
def h_help_untell(bot, reply, args):
    reply('untell [NICK[, NICK[, ...]]]',
    'Cancels all undelivered messages sent using the "tell" command to any of'
    ' the listed NICKs, by any user with your hostmask; or, if no NICK is'
    ' given, cancels your single most recent message. \2!unpage\2 may be used'
    ' as a synonym for \2!untell\2.')

@link('!untell', '!unpage')
def h_untell(bot, id, target, args, full_msg):
    # Secretly, admins may prepend the arguments with the target channel.
    match = re.match(r'(#\S+)\s+(.*)', args)
    if match:
        is_admin = yield auth.check(bot, id)
        if is_admin: channel, args = match.groups()
    elif target:
        channel = target
    else:
        reply(bot, id, target,
            'Error: the "untell" command may only be used in a channel.')
        return # No return with argument allowed in a generator.

    if args:
        untell_nicks(bot, id, target, channel, args)
    else:
        untell_last(bot, id, target, channel)

#-------------------------------------------------------------------------------
def untell_last(bot, id, target, channel):
    state = get_state()
    def would_cancel(msg):
        if msg.channel.lower() != channel.lower(): return False
        if msg.from_id != id: return False
        return True
    cancel_msgs = filter(would_cancel, state.msgs)

    if cancel_msgs:
        last_msg = cancel_msgs[-1]
        state.msgs = [m for m in state.msgs if m is not last_msg]
        put_state(state)
        msg = '1 message to "%s" deleted.' % last_msg.to_nick
    else:
        msg = 'Error: you have no messages to cancel.'
    reply(bot, id, target, msg)

#-------------------------------------------------------------------------------
def untell_nicks(bot, id, target, channel, args):
    state = get_state()
    count = dict()

    def would_cancel(msg, to_nick):
        if msg.channel.lower() != channel.lower(): return False
        if msg.to_nick.lower() != to_nick.lower(): return False
        if msg.from_id != id: return False
        return True

    for to_nick in [n.strip() for n in args.split(',')]:
        msgs = [(would_cancel(m, to_nick), m) for m in state.msgs]
        msgs_cancel = [m for (b, m) in msgs if b]
        msgs_keep = [m for (b, m) in msgs if not b]
        count[to_nick] = len(msgs_cancel)
        if len(msgs_cancel): state.msgs = msgs_keep

    total = sum(count.itervalues())
    msg = '%s message%s deleted.' % (total, 's' if total != 1 else '')

    empty = ['"%s"' % nick for (nick, count) in count.iteritems() if not count]
    if empty:
        list = ', '.join(empty[:-2] + [' or '.join(empty[-2:])])
        msg += (' There were no messages to %s, from %s in %s.'
            % (list, '%s!%s@%s' % tuple(id), channel))

    put_state(state)
    reply(bot, id, target, msg)

#==============================================================================#
@link(('HELP', 'dismiss'))
def h_help_dismiss(bot, reply, args):
    if args and int(args) == 2:
        reply('dismiss [NICK] [!dismiss [NICK] ...]',
        'If NICK is given, dismisses the most recent message left for you by NICK,'
        ' preventing it from being delivered; otherwise, dismisses the most recent'
        ' message left by anybody. Messages may be recovered using \2!undismiss\2.'
        ' Up to 3 additional !dismiss commands may be given on the same line.',
        'NICK may be an IRC nick or a NICK!USER@HOST, may contain the wildcard'
        ' characters * and ?, and may contain alternatives separated by /, as'
        ' specified in \2!help tell 2\2; in which case, the most recent matching'
        ' message is dismissed.')
    else:
        reply('dismiss\2 or \2!dismiss NICK',
        'Dismisses without showing it the most recent message left for you via'
        ' the \2!tell\2 command. If NICK is given, dismisses the most recent'
        ' message left by that nick. For advanced features, see'
        ' \2!help dismiss 2\2. See also: \2!help undismiss\2.')

@link('!dismiss')
@multi('!dismiss', limit=4)
def h_dismiss(bot, id, chan, query, full_msg, reply):
    if chan is None: return reply(
        'Error: the "dismiss" command may only be used in a channel.')

    state = get_state()
    msgs = [m for m in state.msgs
            if m.channel.lower() == chan.lower()
            and (not query or match_id(query, m.from_id))]

    msgs = [m for m in state.msgs if would_deliver(id, chan, m)
            and (not query or match_id(query, m.from_id))]
    if not msgs: return reply(
        'You have no messages%s to dismiss.' % (query and ' from "%s"' % query))

    msg = msgs[-1]
    state.msgs.remove(msg)
    state.dismissed_msgs = [m for m in state.dismissed_msgs
        if (datetime.datetime.utcnow() - m.time_sent).days <= DISMISS_DAYS]
    state.dismissed_msgs.append(msg)

    count = len([m for m in state.msgs if would_deliver(id, chan, m)])
    msg = ('1 message from %s deleted; you now have %s message%s'
       ' (you may reverse this using "undismiss").'
       % (msg.from_id.nick, count, 's' if count != 1 else ''))

    put_state(state)
    reply(msg)

#==============================================================================#
@link(('HELP', 'undismiss'))
def h_help_undismiss(bot, reply, args):
    reply('undismiss\2 or \2!undismiss NICK',
    'Reverses the effect of \2!dismiss\2, restoring the last dismissed message'
    ' from NICK, or from anybody if NICK is not specified. This may be done'
    ' multiple times to restore messages from up to %s days ago. As with'
    ' \2!dismiss\2, NICK may take the form NICK!USER@HOST, and may contain the'
    ' wildcard characters * and ?, and alternatives separated by /.' % DISMISS_DAYS)

@link('!undismiss')
def h_undismiss(bot, id, chan, query, *args):
    if chan == None: return reply(bot, id, chan,
        'Error: the "undismiss" command may only be used in a channel.')

    state = get_state()
    msgs = [m for m in state.dismissed_msgs if would_deliver(id, chan, m)
            and (not query or match_id(query, m.from_id))]
    if not msgs: return reply(bot, id, chan,
        'You have no dismissed messages%s.'
        % (query and ' from "%s"' % query))
    msg = msgs[-1]
    state.dismissed_msgs.remove(msg)
    state.msgs.append(msg)

    count = len([m for m in state.msgs if would_deliver(id, chan, m)])
    msg = ('1 message from %s restored; you now have %s message%s'
        ' (say anything to read %s).'
        % (msg.from_id.nick, count, 's' if count != 1 else '',
        'them' if count != 1 else 'it'))

    put_state(state)
    reply(bot, id, chan, msg)

#==============================================================================#
@link('!read')
def h_read(bot, id, chan, args, full_msg):
    if chan is not None:
        msgs = deliver_msgs(bot, id, chan, explicit=True)
        if not msgs:
            reply(bot, id, chan, 'You have no messages.')
        return

    state = get_state()
    all_msgs = [m for m in state.msgs if would_deliver(id, None, m)
                and m in state.last_notify]

    earliest = dict()
    for msg in all_msgs:
        earliest[msg.channel.lower()] = min(
            msg.time_sent, earliest.get(msg.channel.lower(), msg.time_sent))
    all_msgs = sorted(all_msgs, key=lambda m: earliest[m.channel.lower()])

    if not all_msgs:
        reply(bot, id, chan, 'No messages are available to read.')
        return

    msgs = all_msgs[:MAX_DELIVER_PM]
    remain_msgs = all_msgs[MAX_DELIVER_PM:]
    while any(n <= MAX_DELIVER_CHAN
    for n in Counter(m.channel for m in remain_msgs).itervalues()):
        msgs.append(remain_msgs.pop(0))

    for msg, index in izip(msgs, count(1)):
        tag = '%d/%d: ' % (index, len(all_msgs))
        deliver_msg(bot, id, None, msg, tag=tag)
        yield runtime.sleep(0)

    state = get_state()
    state.msgs = [m for m in state.msgs if m not in msgs]
    put_state(state)

    next_msgs = remain_msgs[:MAX_DELIVER_PM]
    next_remain_msgs = remain_msgs[MAX_DELIVER_PM:]
    while any(n <= MAX_DELIVER_CHAN
    for n in Counter(m.channel for m in next_remain_msgs).itervalues()):
        next_msgs.append(next_remain_msgs.pop(0))

    noun = 'message' if len(remain_msgs) == 1 else 'messages'
    if next_remain_msgs: reply(bot, id, chan,
        'Say \2!read\2 to read the next %d of %d %s.' % (
        len(next_msgs), len(remain_msgs), noun))
    elif next_msgs: reply(bot, id, chan,
        'Say \2!read\2 to read the remaining %d %s.' % (
        len(next_msgs), noun))
    else: reply(bot, id, chan,
        'End of messages.')

#==============================================================================#
@link('!tell?', '!page?')
@admin
def h_tell_list(bot, id, target, args, full_msg):
    output = lambda msg: reply(bot, id, target, msg, prefix=False)
    state = get_state()
    lines = [('#', 'From', 'To', 'Channel', 'Time', 'Message')]
    msgs = state.msgs
    if target:
        msgs = filter(lambda m: m.channel.lower() == target.lower(), msgs)
    rexp = re.compile(re.escape(args), re.I)
    for (num, msg) in izip(count(1), msgs):
        if not any(rexp.search(text) for text in (
            msg.from_id.nick, msg.to_nick, msg.message)): continue
        lines.append((
            str(num),
            '%s!%s@%s' % tuple(msg.from_id),
            msg.to_nick,
            msg.channel,
            msg.time_sent.strftime(DATE_FORMAT_SHORT),
            msg.message))
    lines = util.align_table(lines)
    output('\2' + lines[0])
    map(output, lines[1:])
    output('\2End of List')

#==============================================================================#
@link('!tell+', '!page+')
@admin
def h_tell_add(bot, id, target, args, full_msg):
    args = [a.strip() for a in args.split(',', 4)]
    if len(args) != 5: return reply(bot, id, target,
        'Error: expected: FROM_ID, TO_NICK, CHAN, %s, MESSAGE...'
         % DATE_FORMAT_SHORT)

    [from_id, to_nick, channel, time_sent, message] = args
    try:
        from_id = util.ID(*re.match(r'(.*?)!(.*?)@(.*)$', from_id).groups())
        time_sent = datetime.datetime.strptime(time_sent, DATE_FORMAT_SHORT)
    except Exception as e: return reply(bot, id, target, repr(e))

    msg = Message(from_id=from_id, to_nick=to_nick, channel=channel,
                  time_sent=time_sent, message=message)
    state = get_state()
    state.msgs.append(msg)
    state.msgs.sort(key=lambda m: m.time_sent)
    put_state(state)
    reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-', '!page-')
@admin
def h_tell_remove(bot, id, target, args, full_msg):
    state = get_state()
    msgs = state.msgs
    if target:
        msgs = filter(lambda m: m.channel.lower() == target.lower(), msgs)
    remove_msgs = []
    try:
        for match in re.finditer(r'\S+', args):
            index = int(match.group()) - 1
            remove_msgs.append(msgs[index])
        for msg in remove_msgs:
            state.msgs.remove(msg)
    except Exception as e:
        return reply(bot, id, target, repr(e))
    put_state(state)
    reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-clear', '!page-clear')
@admin
def h_tell_clear(bot, id, target, args, full_msg):
    put_state(State())
    reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-undo', '!page-undo')
@admin
def h_tell_undo(bot, id, target, args, full_msg):
    try:
        undo_state()
    except HistoryEmpty:
        reply(bot, id, target, 'Error: no undo state is available.')
    else:
        reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-redo', '!page-redo')
@admin
def h_tell_undo(bot, id, target, args, full_msg):
    try:
        redo_state()
    except HistoryEmpty:
        reply(bot, id, target, 'Error: no redo state is available.')
    else:
        reply(bot, id, target, 'Done.')

#==============================================================================#
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    notify_msgs(bot, id, chan)

@link('MESSAGE')
def h_message(bot, id, target, msg):
    if target:
        deliver_msgs(bot, id, target)

@link('CMD_IGNORED')
def h_cmd_ignored(cmd, bot, id, target, args, full_msg):
    if target:
        deliver_msgs(bot, id, target)

@link('OTHER_NICK_CHAN')
def h_nick(bot, id, new_nick, chan):
    state = get_state()
    old_id = util.ID(*id)
    new_id = util.ID(new_nick, old_id.user, old_id.host)

    last_notify_max = time.time() - MIN_NICKCHANGE_NOTIFY_INTERVAL_S
    def would_notify(msg):
        if not would_deliver(new_id, chan, msg): return False
        return msg not in state.last_notify \
            or state.last_notify[msg] < last_notify_max

    if any(would_notify(m) for m in state.msgs):
        return notify_msgs(bot, new_id, chan)

#==============================================================================#
# Notify `id' of messages left for them in `chan', if any.
def notify_msgs(bot, id, chan):
    state = get_state()
    msgs = filter(lambda m: would_deliver(id, chan, m), state.msgs)
    if not msgs:
        return

    noun, pronoun = ('messages', 'them') if len(msgs) > 1 else ('message', 'it')
    if len(msgs) <= MAX_DELIVER_CHAN:
        reply(bot, id, chan,
            'You have %s %s; say anything to read %s.' % (
            len(msgs), noun, pronoun))
    else:
        reply(bot, id, chan,
            'You have %s %s; use "\2/msg %s !read\2" to read %s.' % (
            len(msgs), noun, bot.nick, pronoun))

    for msg in msgs:
        set_last_notify(msg, state)
    set_state(state)

#==============================================================================#
# Deliver to `id' any messages left for them in `chan'; unless the number of
# such messages exceeds MAX_DELIVER_CHAN, in which case instruct `id' to read
# them by PM; unless explicit is False and the recipient has already been
# notified of all such messages, in which case do not issue any notification.
# In all cases, return a list of the messages in question.
def deliver_msgs(bot, id, chan, explicit=False):
    state = get_state()
    msgs = [(would_deliver(id, chan, m), m) for m in state.msgs]
    msgs_deliver = [m for (b, m) in msgs if b]
    msgs_keep = [m for (b, m) in msgs if not b]

    if 0 < len(msgs_deliver) <= MAX_DELIVER_CHAN:
        # Deliver each message in the channel.
        for msg in msgs_deliver:
            deliver_msg(bot, id, chan, msg)
        state.msgs = msgs_keep
        set_state(state)
    elif (len(msgs_deliver) > MAX_DELIVER_CHAN
    and (explicit or any(m not in state.last_notify for m in msgs_deliver))):
        # There are too many messages; tell the recipient to read them by PM.
        notify_msgs(bot, id, chan)

    return msgs_deliver

#==============================================================================#
# Unconditionally deliver `msg' to `id' in `chan', or by PM if `chan' is None.
def deliver_msg(bot, id, chan, msg, tag=''):
    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False
    d_mins, d_secs = divmod(delta.seconds, 60)
    d_hours, d_mins = divmod(d_mins, 60)

    reply(bot, id, chan, '%s%s said%s on %s UTC (%s ago):' % (
        tag,
        '%s!%s@%s' % tuple(msg.from_id),
        (' in %s' % msg.channel) if chan is None else '',
        msg.time_sent.strftime('%d %b %Y, %H:%M'),
        '%sd, %02d:%02d:%02d' % (delta.days, d_hours, d_mins, d_secs)))
    reply(bot, id, chan, "<%s> %s" % (msg.from_id.nick, msg.message),
        prefix=False)

    bot.drive('TELL_DELIVERY', bot, msg.from_id, id, chan, msg.message)
    return True

@link('TELL_DELIVERY')
def h_tell_delivery(bot, from_id, to_id, chan, msg):
    yield sign('PROXY_MSG', bot, from_id, chan, msg)

#==============================================================================#
# Returns True if `msg' would be delivered at this time to `id' in `chan',
# or otherwise returns False. Alternatively, if `chan' is None, returns True if
# the message would be delivered in any channel.
def would_deliver(id, chan, msg):
    if chan is not None and msg.channel.lower() != chan.lower(): return False
    if not match_id(msg.to_nick, id): return False
    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False
    return True

#==============================================================================#
# Returns True if any '/'-separated part of `query', interpreted as a wildcard
# expression, matches either the nick or or the nick!user@host of the given id.
def match_id(query, id):
    id_str = '%s!%s@%s' % tuple(id) if re.search(r'!|@', query) else id.nick
    for part in query.split('/'):
        rexp = part if '$' in part else wc_to_re(part)
        if re.match(rexp, id_str, re.I) is not None: return True
    return False

#===============================================================================
# Returns True iff the two given IDs are considered to belong to the same user,
# i.e. if they have the same host and the same username, or they have the same
# host and either username starts with a tilde.
def same_sender(id1, id2):
    return id1.host.lower() == id2.host.lower() and \
           (id1.user.lower() == id2.user.lower() or \
            id1.user.startswith('~') or id2.user.startswith('~'))
