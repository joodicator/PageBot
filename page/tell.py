#==============================================================================#
# tell.py - provides !tell, and related commands, to allow users to leave each
# other messages in an IRC channel.

#==============================================================================#
# Possible extensions:
#
# - Allow multiple senders to be specified for !dismiss and !undismiss.
#
# - Allow "private" messages: if user A is in channel #C and tells the bot by,
#   PM "!tell #C B MSG", user B will be delivered MSG by PM next time they are
#   in channel C, provided that user A is also in channel #C.
#
# - Place some limit on the number of messages a single user can leave, possibly
#   also per recipient (if it's possible to identify "recipients"...)

from collections import namedtuple
from copy import deepcopy
from itertools import *
import pickle as pickle
import traceback
import os.path
import datetime
import time
import re

import untwisted.magic

from message import reply
from util import multi, wc_to_re
from auth import admin
import identity
import channel
import util
import auth


#==============================================================================#
link, install, uninstall = util.LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'auth', 'identity')

identity.add_credentials('tell.Broose',
    ('nickserv',   'Broose'),
    ('access',     'Broose'),
    ('prev_hosts', 2))

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

# last_notify[msg] = time.time()
# when msg's recipient was last notified of it.
last_notify = dict()

#-------------------------------------------------------------------------------
# A saved message kept by the system.
Message = namedtuple('Message',
    ('time_sent', 'channel', 'from_id', 'to_nick', 'message'))
Message.__getstate__ = lambda *a, **k: None

#-------------------------------------------------------------------------------
# The plugin's persistent state object.
class State(object):
    def __init__(self):
        self.msgs = []
        self.dismissed_msgs = []
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

# Mark that msg's receipient has been notified of it now.
def set_last_notify(msg, state):
    last_notify[msg] = time.time()
    for other_msg in last_notify.keys():
        if other_msg not in state.msgs:
            last_notify.pop(other_msg, None)

#==============================================================================#
@link('HELP*')
def h_help_tell_short(bot, reply, args):
    reply('tell NICK [...] MESSAGE',
    'When NICK is next seen in this channel, MESSAGE will be delivered to them.')

@link(('HELP', 'tell'))
def h_help_tell(bot, reply, args):
    reply('tell NICK MESSAGE')
    reply('tell NICK[, NICK[, ...]]: MESSAGE')
    reply('',
    'Leaves a message for the given NICK, or for each of the listed NICKs,'
    ' so that it will be delivered to them when next seen in this channel.',
    'If NICK contains any occurrence of ! or @, it will be matched against'
    ' the full NICK!USER@HOST of the recipient, instead of just their nick.'
    ' If NICK contains the wildcard characters * or ?, these will match any'
    ' sequence of 0 or more characters, or exactly 1 character, respectively.',
    'Alternatively, if NICK contains the character $, it will be interpreted'
    ' as a Python 2 regular expression using re.match() semantics.'
    ' (see: http://docs.python.org/2/library/re.html).')

@link('!tell')
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

    sent_count = len(to_nicks)
    same_sent = [m for m in state.msgs if same_sender(m.from_id, id)
                 and m.channel.lower() == channel.lower()]
    if len(same_sent) > MAX_SENT:
        reply(bot, id, target,
            'Error: you may leave no more than %d messages at once.' % MAX_SENT)
        return
    if to_nick.endswith('$'):
        same_recv = [m for m in same_sent if m.to_nick.endswith('$')]
        if len(same_recv) > MAX_SENT_RE:
            reply(bot, id, target,
                'Error: you may leave no more than %d regex-addressed messages'
                ' at once.' % (MAX_SENT_RE))
            return
    else:
        norm_recv = lambda r: re.sub(r'\*+', r'*', r).lower()
        norm_nicks = map(norm_recv, to_nicks)
        same_recv = [m for m in same_sent if norm_recv(m.to_nick) in norm_nicks]
        if len(same_recv) > MAX_SENT_WC:
            reply(bot, id, target,
                'Error: you may leave no more than %d messages for "%s"'
                ' at once.' % (MAX_SENT_WC, same_recv[0].to_nick))
            return

    put_state(state)

    father = yield identity.check_access(bot, id, 'tell.Broose')
    affirm = 'Yes, father' if father else 'It shall be done'

    if sent_count > 1: reply(bot, id, target,
        '%s (%s messages sent).' % (affirm, sent_count))
    else: reply(bot, id, target,
        '%s (1 message sent to "%s").' % (affirm, to_nick))

#==============================================================================#
@link('HELP')
def h_help_untell_short(bot, reply, args):
    reply('untell [NICK ...]',
    'Cancels your last "tell" message, or all messages to given NICKs.')

@link(('HELP', 'untell'))
def h_help_untell(bot, reply, args):
    reply('untell [NICK[, NICK[, ...]]]',
    'Cancels all undelivered messages sent using the "tell" command to any of'
    ' the listed NICKs, by any user with your hostmask; or, if no NICK is'
    ' given, cancels your single most recent message.')

@link('!untell')
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
        msg = ('1 message (to "%s"; the most recent of %s such message%s)'
            ' deleted.' % (last_msg.to_nick, len(cancel_msgs),
            's' if len(cancel_msgs) > 1 else ''))
    else:
        msg = 'Error: you have no messages to cancel.'
    reply(bot, id, target, msg)

#-------------------------------------------------------------------------------
def untell_nicks(bot, id, target, channel, args):
    state = get_state()
    count = dict()

    def would_cancel(msg, to_nick):
        if msg.channel.lower() != channel.lower(): return False
        if msg.to_nick != to_nick: return False
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
@link('HELP')
def h_help_dismiss_short(bot, reply, args):
    reply('dismiss [NICK]',
    'Cancels delivery of the last message left for you.')

@link(('HELP', 'dismiss'))
def h_help_dismiss(bot, reply, args):
    reply('dismiss [NICK] [!dismiss [NICK] ...]',
    'If NICK is given, dismisses the most recent message left for you by NICK,'
    ' preventing it from being delivered; otherwise, dismisses the most recent'
    ' message left by anybody. Messages may be recovered using "undismiss".'
    ' Up to 3 additional !dismiss commands may be given on the same line.',
    'NICK may be an IRC nick or a NICK!USER@HOST, may contain the wildcard'
    ' characters * and ?, and may be a Python 2 regular expression containing'
    ' the character $, as specified in "help tell"; in which case, the most'
    ' recent matching message is dismissed.')

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
@link('!tell?')
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
@link('!tell+')
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
@link('!tell-')
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
@link('!tell-clear')
@admin
def h_tell_clear(bot, id, target, args, full_msg):
    put_state(State())
    reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-undo')
@admin
def h_tell_undo(bot, id, target, args, full_msg):
    try:
        undo_state()
    except HistoryEmpty:
        reply(bot, id, target, 'Error: no undo state is available.')
    else:
        reply(bot, id, target, 'Done.')

#==============================================================================#
@link('!tell-redo')
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
    if target: deliver_msgs(bot, id, target)

@link('OTHER_NICK_CHAN')
def h_nick(bot, id, new_nick, chan):
    state = get_state()
    old_id = util.ID(*id)
    new_id = util.ID(new_nick, old_id.user, old_id.host)

    last_notify_max = time.time() - MIN_NICKCHANGE_NOTIFY_INTERVAL_S
    def would_notify(msg):
        if not would_deliver(new_id, chan, msg): return False
        return msg not in last_notify or last_notify[msg] < last_notify_max

    if any(would_notify(m) for m in state.msgs):
        return notify_msgs(bot, new_id, chan)

#==============================================================================#
# Notify `id' of messages left for them in `chan', if any.
def notify_msgs(bot, id, chan):
    state = get_state()
    msgs = filter(lambda m: would_deliver(id, chan, m), state.msgs)
    if msgs:
        reply(bot, id, chan, 'You have %s message%s; say anything to read %s.'
            % ((len(msgs),'s','them') if len(msgs) > 1 else (len(msgs),'','it')))
        for msg in msgs:
            set_last_notify(msg, state)

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

    bot.drive('TELL_DELIVERY', bot, msg.from_id, id, chan, msg.message)
    return True

#==============================================================================#
# Returns True if `msg' would be delivered at this time to `id' in `chan',
# or otherwise returns False.
def would_deliver(id, chan, msg):
    if msg.channel.lower() != chan.lower(): return False
    if not match_id(msg.to_nick, id): return False
    delta = datetime.datetime.utcnow() - msg.time_sent
    if delta.total_seconds() < 1: return False    
    return True

#==============================================================================#
# Returns True if `query', which is is a wildcard expression or (if it contains
# '$'), a regular expression matching either a nick or a nick!user@host,
# matches the given id.
def match_id(query, id):
    id_str = '%s!%s@%s' % tuple(id) if re.search(r'!|@', query) else id.nick
    rexp = query if '$' in query else wc_to_re(query)
    return re.match(rexp, id_str, re.I) is not None

#===============================================================================
# Returns True iff the two given IDs are considered to belong to the same user,
# i.e. if they have the same host and the same username, or they have the same
# host and either username starts with a tilde.
def same_sender(id1, id2):
    return id1.host.lower() == id2.host.lower() and \
           (id1.user.lower() == id2.user.lower() or \
            id1.user.startswith('~') or id2.user.startswith('~'))
