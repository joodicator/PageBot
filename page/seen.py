from itertools import *
from collections import namedtuple
import traceback
import calendar
import datetime
import time
import json
import re
import os.path

from util import LinkSet
from message import reply
import channel
import identity
import util
import auth

link, install, uninstall = LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'channel', 'identity')

STATE_FILE = 'state/seen.json'
MAX_RECORDS = 100000
PRUNE_THRESHOLD = 100

EVENT_TYPES = 'message', 'action', 'exit'

#===============================================================================
# global_state[chan.lower()]['nick!user@host'.lower()] = {
#    'exit':    { time: T, params: PE },
#    'action':  { time: T, params: PA },
#    'message': { time: T, params: PM },
#    'id_case': 'nick!user@host'
# } where
#     T = time.time()
#     PE in ['part', pmsg], ['quit', qmsg], ['kicked', kmsg, op_mask]
#     PA in ['mode', modes], ['topic', topic], ['kick', kmsg, knick]
#     PM in ['message', msg], ['notice', msg]
global_state = None

#-------------------------------------------------------------------------------
def get_state():
    global global_state
    if global_state is not None:
        return global_state
    global_state = dict()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as file:
                global_state = json.load(file)
        except (ValueError, IOError):
            traceback.print_exc()
    global_state = util.recursive_encode(global_state, 'utf-8')
    return global_state

#-------------------------------------------------------------------------------
def put_state(new_state):
    global global_state
    global_state = prune_state(new_state)
    try:
        data = json.dumps(global_state, ensure_ascii=False)
        with open(STATE_FILE, 'w') as file:
            file.write(data)
    except (ValueError, IOError):
        traceback.print_exc()

#-------------------------------------------------------------------------------
def prune_state(state):
    if sum(imap(len, state)) <= MAX_RECORDS + PRUNE_THRESHOLD:
        return state
    new_state = dict()
    records = sorted(
        ((c,i,ir) for (c,cr) in state.iteritems() for (i,ir) in cr.iteritems()),
        key=lambda t: max(t[2][et]['time'] for et in EVENT_TYPES if et in t[2]),
        reverse=True)
    for chan, id, record in records[:MAX_RECORDS]:
        if chan not in new_state: new_state[chan] = dict()
        new_state[chan][id] = record
    return new_state

#===============================================================================
@link('HELP*')
def h_help_seen_short(bot, reply, args):
    reply('seen NICK', 'Tells when NICK was last seen in this channel.')

@link(('HELP', 'seen'))
def h_help_seen(bot, reply, args):
    reply('seen NICK\2 or \2!seen NICK!USER@HOST',
    'Tells how long ago any user was seen in the channel with the given NICK,'
    ' or matching the given hostmask. Both forms may contain the wildcard'
    ' characters * and ?, which stand for zero or more characters and exactly'
    ' one character, respectively. Examples: "!seen Alice",'
    ' "!seen *@*.alicedsl.se".')

@link('!seen')
def h_seen(bot, id, target, args, full_msg):
    chan = None
    match = re.match(r'(#\S+)\s*(.*)', args)
    if match:
        is_admin = yield auth.check(bot, id)
        if is_admin:
            chan = match.group(1).lower()
            args = match.group(2)
    if not chan and target:
        chan = target.lower()
    elif not chan:
        return

    if not args: return

    if re.search(r'!|@', args):
        pattern = util.wc_to_re(args)
    else:
        pattern = util.wc_to_re('%s!*@*' % args)

    # matching_nicks[nick.lower()] = (max_time, id_case)
    matching_nicks = dict()

    in_channel = False
    for cnick in channel.track_channels.get(chan, ()):
        cmask = yield identity.get_hostmask(bot, cnick)
        if re.match(pattern, cmask, re.I):
            cid = util.ID(*re.match(r'(.*?)!(.*?)@(.*)', cmask).groups())
            matching_nicks[cid.nick.lower()] = (None, cid)
            in_channel = True
            continue

    state = get_state()
    combined_record = dict()
    for rmask, record in state.get(chan, dict()).iteritems():
        if re.match(pattern, rmask, re.I):
            if 'id_case' in record:
                rmask = record['id_case'].encode('utf8')
            rid = util.ID(*re.match(r'(.*?)!(.*?)@(.*)', rmask).groups())
            record = attribute_record_to(record, rid)
            combined_record = combine_records(combined_record, record)

            max_time = max(
                record[et]['time'] for et in EVENT_TYPES if et in record)
            if (rid.nick.lower() not in matching_nicks
            or matching_nicks[rid.nick.lower()][0] is not None
            and matching_nicks[rid.nick.lower()][0] < max_time):
                matching_nicks[rid.nick.lower()] = (max_time, rid)

    def nick_sort_key(nick):
        max_time = matching_nicks[nick.lower()][0]
        return -max_time if max_time is not None else None
    nicks = sorted(matching_nicks.iterkeys(), key=nick_sort_key)

    if nicks:
        if len(matching_nicks) > 4:
            nicks = nicks[:3]
            nicks += ['one of %d others' % (len(matching_nicks)-3)]
        id_name = ''.join('%s%s' % (
            ' or ' if i > 0 and i+1 == len(nicks) else ', ' if i > 0 else '',
            '\2%s\2' % matching_nicks[nick][1].nick
                if nick in matching_nicks else nick
        ) for (i, nick) in izip(count(), nicks))
    else:
        id_name = args

    reply(bot, id, target, record_string(
        id_name    = id_name,
        record     = combined_record,
        now        = time.time(),
        in_channel = in_channel,
        plural     = len(nicks) > 1))

#-------------------------------------------------------------------------------
# Combines the given records into one, taking the most recent events from each
# and discarding all other information.
def combine_records(*records):
    combined_record = dict()
    for et in EVENT_TYPES:
        events = [r[et] for r in records if et in r]
        if not events: continue
        combined_record[et] = max(events, key=lambda er: er['time'])
    return combined_record

#-------------------------------------------------------------------------------
# Return a copy of the given record, annotated so that each event contains
# an attribute 'id' indicating that the given id is the subject of the event.
def attribute_record_to(record, id):
    record = dict(record)
    for et in EVENT_TYPES:
        if et not in record: continue
        event = dict(record[et])
        event['id'] = id
        record[et] = event
    return record

#-------------------------------------------------------------------------------
# Given the record of appearances of an identity in a channel, returns a string
# describing the relative times of the identity's last appearance(s). If
# in_channel is given as True, the identity is assumed to be in the channel. If
# plural is given as true, id_name is assumed to refer to multiple persons.
# Any events with an 'id' attribute (as generated by attribute_record_to) will
# be annotated as appropriate with this id.
def record_string(id_name, record, now=None, in_channel=False, plural=False):
    events = present_record(record or dict(), now, in_channel)
    if not events:
        if in_channel: return (
            '%s is in the channel; however, there is no record of previous'
            ' activity.' % id_name)
        else: return (
            'There is no record of "%s" in this channel.' % id_name)
    else:
        ids = set(('%s!%s@%s' % er.get('id', '')).lower() for (et,er) in events)
        dup_id = len(ids) == 1 and len(events) > 1

        verbs = ', '.join('%s%s%s %s' % (
            'and ' if i>0 and i+1 == len(events) else '',
            event_string(et, er['params']),
            ' (as %s!%s@%s)' % er['id'] if not dup_id and 'id' in er else '',
            relative_time_string(relative_time(er['time'], now))
        ) for (i, (et,er)) in izip(count(), events))

        if dup_id and 'id' in events[0][1]:
            verbs = '(as %s!%s@%s) %s' % (events[0][1]['id'] + (verbs,))

        if in_channel: return (
            '%s is in the channel, and %s last seen %s.'
             % (id_name, 'one was' if plural else 'was', verbs))
        else: return (
            '%s was last seen here %s.' % (id_name, verbs))

#-------------------------------------------------------------------------------
# Given the record of appearances of an identity in a channel, returns a list of
# (event_type, event_record) in the order in which they should be mentioned
# when presenting the record to the user. If in_channel is given as True, the
# output is specialised for an identity currently in the channel.
def present_record(record, now=None, in_channel=False):
    if now is None: now = time.time()
    event_types = ('message', 'action') if in_channel \
             else ('message', 'action', 'exit')

    # Consider events from most recent to least.
    events = sorted(
        ((et, record[et]) for et in event_types if et in record),
        key=lambda e: e[1]['time'], reverse=True)

    # Discard all events occurring before the most important event on record.
    if events:
        events = events[:1+min(range(len(events)),
            key=lambda i: event_types.index(events[i][0]))]

    # Further discard any event occurring sufficiently soon after another event.
    def ignore_event_after((et1, er1), (et2, er2)):
        return max(1, min(86400, now-er2['time']))/(er1['time']-er2['time']) > 6
    events = [events[i] for i in range(len(events))
        if i+1 >= len(events) or not ignore_event_after(events[i], events[i+1])]
    
    return events

#-------------------------------------------------------------------------------
# Returns a present tense verb phrase describing the given event.
def event_string(event_type, event_params):
    if event_type == 'message':
        return 'talking'
    elif event_type == 'action':
        if event_params[0] == 'mode':
            return 'setting a channel mode'
        elif event_params[0] == 'topic':
            return 'setting the topic'
        elif event_params[0] == 'kick':
            return 'kicking a user'
        elif event_params[0] == 'nick_from':
            return 'changing their nick'
        elif event_params[0] == 'nick_to':
            return 'changing their nick'
    elif event_type == 'exit':
        if event_params[0] == 'quit':
            return 'quitting the network'
        elif event_params[0] == 'part':
            return 'leaving the channel'
        elif event_params[0] == 'kicked':
            return 'being kicked from the channel'

#-------------------------------------------------------------------------------
RelativeTime = namedtuple('RelativeTime',
    ('years', 'months', 'days', 'hours', 'minutes', 'seconds', 'microseconds'))

#-------------------------------------------------------------------------------
# Formats a RelativeTime instance as a user-readable string.
def relative_time_string(rtime):
    s = lambda x: 's' if x != 1 else ''
    if rtime.years: return '\2%d year%s and %d month%s\2 ago' % (
        rtime.years, s(rtime.years), rtime.months, s(rtime.months))
    elif rtime.months: return '\2%d month%s and %d day%s\2 ago' % (
        rtime.months, s(rtime.months), rtime.days, s(rtime.days))
    elif rtime.days: return '\2%d day%s and %d hour%s\2 ago' % (
        rtime.days, s(rtime.days), rtime.hours, s(rtime.hours))
    elif rtime.hours: return '\2%d hour%s and %d minute%s\2 ago' % (
        rtime.hours, s(rtime.hours), rtime.minutes, s(rtime.minutes))
    elif rtime.minutes: return '\2%d minute%s and %d second%s\2 ago' % (
        rtime.minutes, s(rtime.minutes), rtime.seconds, s(rtime.seconds))
    elif rtime.seconds: return '\2%d second%s\2 ago' % (
        rtime.seconds, s(rtime.seconds))
    else: return 'less than a second ago'

#-------------------------------------------------------------------------------
# Given a timestamp generated by time.time(), returns a RelativeTime instance
# describing how far in the past it is relative to the current time.
def relative_time(then, now=None):
    if now is None: now = time.time()
    then = datetime.datetime.fromtimestamp(then)
    now = datetime.datetime.fromtimestamp(now)

    delta, days, months, years = datetime.timedelta(), 0, 0, 0

    delta += now - datetime.datetime.combine(now.date(), then.time())
    days += delta.days
    delta -= datetime.timedelta(delta.days)

    days += now.day - then.day
    if days < 0:
        months -= 1
        days += calendar.monthrange(then.year, then.month)[1]

    months += now.month - then.month
    if months < 0:
        years -= 1
        months += 12
    years += months // 12
    months = months % 12

    years += now.year - then.year

    hours = delta.seconds // 3600
    minutes = (delta.seconds // 60) % 60
    seconds = delta.seconds % 60

    return RelativeTime(
        years, months, days, hours, minutes, seconds, delta.microseconds)

#===============================================================================
@link('SOME_PART',          a=lambda bot, id, chan, pmsg:
    (bot, id, None, chan,       'exit', ('part', pmsg)))
@link('SOME_KICKED',        a=lambda bot, knick, op_id, chan, kmsg:
    (bot, None, knick, chan,    'exit', ('kicked', kmsg, '%s!%s@%s'%op_id)))
@link('OTHER_QUIT_CHAN',    a=lambda bot, id, qmsg, chan:
    (bot, id, None, chan,       'exit', ('quit', qmsg)))
@link('MODE',               a=lambda bot, source, chan, *args:
    (bot, source, None, chan,   'action', ('mode', ' '.join(args))))
@link('TOPIC',              a=lambda bot, source, chan, topic:
    (bot, source, None, chan,   'action', ('topic', topic)))
@link('SOME_KICKED',        a=lambda bot, knick, op_id, chan, kmsg:
    (bot, op_id, None, chan,    'action', ('kick', kmsg, knick)))
@link('SOME_NICK_CHAN',     a=lambda bot, id, nnick, chan:
    (bot, id, None, chan,       'action', ('nick_to', nnick)))
@link('SOME_NICK_CHAN',     a=lambda bot, id, nnick, chan:
    (bot, None, nnick, chan,    'action', ('nick_from', id.nick)))
@link('MESSAGE',            a=lambda bot, id, chan, msg:
    (bot, id, None, chan,       'message', ('message', msg)))
@link('COMMAND',            a=lambda bot, id, chan, event, body, msg:
    (bot, id, None, chan,       'message', ('message', msg)))
@link('SEND_MSG',           a=lambda bot, chan, msg, kwds:
    (bot, None, bot.nick, chan, 'message', ('message', msg)))
@link('UNOTICE',            a=lambda bot, id, chan, msg:
    (bot, id, None, chan,       'message', ('notice', msg)))
def h_event(*args, **kwds):
    bot, id, nick, chan, event_type, params = kwds['a'](*args)
    if chan is None or not chan.startswith('#'): return
    chan = chan.lower()

    if id:
        if not isinstance(id, tuple): return
        id = '%s!%s@%s' % id
    else:
        id = yield identity.get_hostmask(bot, nick)
        if not id: return
        
    state = get_state()
    if chan not in state: state[chan] = dict()
    if id.lower() not in state[chan]:
        state[chan][id.lower()] = dict()
    state[chan][id.lower()][event_type] = {
        'time': time.time(), 'params': params }
    state[chan][id.lower()]['id_case'] = id
    put_state(state)
