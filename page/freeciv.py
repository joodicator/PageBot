from __future__ import print_function

from cStringIO import StringIO
from collections import namedtuple, defaultdict
from copy import deepcopy
from itertools import imap, izip, count, chain
import socket
import struct
import sys
import zlib
import array
import operator
import re
import json
import traceback
import os.path
import time

from untwisted.magic import sign
import untwisted.mode
import untwisted.event
import untwisted.utils.common
import untwisted.utils.std

from util import UserError
from message import reply
import runtime
import channel
import auth
import util
import bridge
import identity

CONF_FILE = 'state/freeciv.json'
CONF_VERSION = 2
MAX_CHAN_SERVERS = 10
DEFAULT_PORT = 5556
FC_LOOP_INTERVAL_S = 15 # 15 seconds
MIN_RECONNECT_DELAY_S = 15 # 15 seconds
MAX_RECONNECT_DELAY_S = 3600 # 1 hour
TURN_NOTIFY_INTERVAL_S = 12 * 3600 # 12 hours
INDIVIDUAL_TURN_NOTIFY_INTERVAL_S = 0
RECV_TIMEOUT_S = 3 * 60 # 3 minutes

Version = namedtuple('Version', ('major_version', 'minor_version', 'patch_version'))
DEFAULT_VERSION = Version(2, 6, 0)
AUX_CAPABILITY = 'techloss_forgiveness'
STAGE_NEW, STAGE_INITIAL, STAGE_ACCEPTED, STAGE_LOADED = range(4)
PACKETS = {}

COMPRESSION_BORDER = 0x4001
JUMBO_SIZE = 0xFFFF
MAX_LEN_MSG = 1536
MAX_LEN_PASSWORD = 512
MAX_LEN_USERNAME = 48 # Hardcoded in Freeciv's packets.def.
MAX_LEN_NAME = 48
MAX_LEN_CAPSTR = 512
MAX_LEN_ADDR = 256
MAX_GRANARY_INIS = 24
MAX_CALENDAR_FRAGMENTS = 52
MAX_NUM_ITEMS = 200
MAX_NUM_PLAYER_SLOTS = 160
A_LAST = MAX_NUM_ITEMS
B_LAST = MAX_NUM_ITEMS
PHASE_INVALIDATED = -1
PHASE_UNKNOWN = -2

ab_link = util.LinkSet()
fc_link = util.LinkSet()
fc_link.link_module(untwisted.utils.std)
fc_link.link(untwisted.event.DATA, untwisted.utils.common.append)
fc_mode = None

conf_loaded = False
conf = {
    'channels': {
#       '#CHAN': {
#           'SERVER_NAME': {
#               'address': 'HOST:PORT',
#               'flags': ['set_by_admin' | 'debug', ...] = [],
#           },
#           ...
#       },
#       ...
     },
    'servers': {
#       'HOST:PORT': {
#           'username':         USERNAME:str = None,
#           'password':         PASSWORD:str = None,
#           'last_turn_info':   [PHASE_MODE:int, TURN:int, PHASE:int] = [None]*3,
#           'connect_retries':  RETRIES:int = 0,
#           'last_error':       'ERROR_STRING' = None,
#           'last_error_time':  UNIX_SECONDS = None,
#           'last_notify_time': UNIX_SECONDS = None,
#           'last_individual_notify_time': {
#               'USERNAME': UNIX_SECONDS = None,
#               ...
#           } = {}
#       },
#       ...
     },
    'conf_version': CONF_VERSION,
}
connections = {}

TurnInfo = namedtuple('TurnInfo', ('phase_mode', 'turn', 'phase'))

class FreecivState(object):
    data_version = 2
    def __init__(self, name):
        self.name = name
        self.version = DEFAULT_VERSION
        self.debug = False
        self.stage = STAGE_NEW
        self.conn_id = None
        self.last_recv = {}
        self.last_send = {}
        self.chunk_rem = 0
        self.chunk_buf = ''
        self.last_recv_time = None

def install(bot):
    global fc_mode
    ab_link.install(bot)
    if fc_mode is None: fc_mode = untwisted.mode.Mode()
    fc_link.install(fc_mode)
    if not conf_loaded: load_conf()
    for conn in connections.itervalues():
        update_phase(conn.freeciv_state)
    fc_mode.drive('FC_LOOP')

def reload(prev):
    global conf_loaded, fc_mode, conf
    if hasattr(prev, 'conf') and isinstance(prev.conf, dict) \
    and getattr(prev, 'conf_loaded', False) and all(k in prev.conf for k in conf):
        if prev.conf['conf_version'] == conf['conf_version']:
            conf = deepcopy(prev.conf)
        else:
            conf = upgrade_conf(prev.conf)
        conf_loaded  = True

    if not hasattr(prev, 'connections') or not isinstance(prev.connections, dict):
        return

    if not hasattr(prev, 'FreecivState') \
    or not hasattr(prev.FreecivState, 'data_version') \
    or prev.FreecivState.data_version != FreecivState.data_version:
        compatible = False
    else:
        compatible = True

    fc_mode = untwisted.mode.Mode()
    for address, work in prev.connections.iteritems():
        conf_username = conf['servers'][address]['username']
        if compatible and address in conf['servers'] \
        and conf_username in (None, work.freeciv_state.username):
            work.destroy()
            new_work = untwisted.network.Work(fc_mode, work.sock)
            new_work.freeciv_state = FreecivState(name=address)
            new_work.freeciv_state.__dict__.update(work.freeciv_state.__dict__)
            new_work.freeciv_state.debug = 'debug' in get_server_flags(address)
            connections[address] = new_work
        else:
            if hasattr(work.freeciv_state, 'name'):
                report(work.freeciv_state.name,
                    'Disconnected from server: client software updated.')
            disconnect(work)

def reload_uninstall(bot):
    uninstall(bot, reload=True)

def uninstall(bot, reload=False):
    try:
        global fc_mode
        ab_link.uninstall(bot)
        fc_link.uninstall(fc_mode)
        del fc_mode
    finally:
        if not reload:
            for work in connections.itervalues():
                disconnect(work)
            connections.clear()

def connect(bot, address, server_conf):
    if address in connections:
        raise Exception('%r is already connected.' % address)
    host, port = re.match(r'(.*):(\d+)$', address).groups()
    username, password = server_conf['username'], server_conf['password']
    if username is None: username = bot.conf['nick']
    flags = get_server_flags(address)
    connect_raw(host, int(port), username, password,
                allow_local = 'set_by_admin' in flags,
                debug = 'debug' in flags)

def connect_raw(host, port, username, password, allow_local=False, debug=False):
    state = FreecivState(name = '%s:%d' % (host.lower(), port))
    state.debug, state.username, state.password = debug, username, password
    try:
        fam, typ, pro, cnm, adr = \
            socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]
        if not allow_local and not util.is_global_address_raw(fam, adr):
            raise UserError('Access denied: %s is not a public internet'
                            ' address.' % state.name)
        work = untwisted.network.Work(fc_mode, socket.socket(fam, typ, pro))
        work.setblocking(0)
        work.freeciv_state = state
        connections[state.name] = work
        work.connect_ex(adr)
    except (socket.error, UserError) as e:
        traceback.print_exc()
        fc_mode.drive('FC_CONN_ERR', state, e)
    else:
        state.stage = STAGE_INITIAL
        fc_mode.drive(('FC_SEND', PACKET_SERVER_JOIN_REQ), work,
            username = username,
            capability = '+Freeciv-{1}.{2}-network {0}'.format(
                             AUX_CAPABILITY, *state.version),
            version_label='',
            **state.version._asdict())
        state.last_recv_time = time.time()

def get_server_flags(address):
    return {flag for cconf in conf['channels'].itervalues()
        for csconf in cconf.itervalues() if csconf['address'] == address
        for flag in csconf.get('flags', ())}

def disconnect(work):
    work.destroy()
    try: work.shutdown(socket.SHUT_RDWR)
    except socket.error: pass
    try: work.close()
    except socket.error: pass

def load_conf():
    global conf, conf_loaded
    cur_version = conf['conf_version']
    if os.path.exists(CONF_FILE):
        try:
            with open(CONF_FILE, 'r') as file:
                conf = util.recursive_encode(json.load(file), 'utf8')
        except IOError:
            traceback.print_exc()
    if conf['conf_version'] < CONF_VERSION:
        conf = upgrade_conf(conf)
    elif conf['conf_version'] > CONF_VERSION:
        raise ValueError('conf_version=%r is unknown' % conf['conf_version'])
    conf_loaded = True

def save_conf():
    with open(CONF_FILE, 'w') as file:
       json.dump(conf, file, indent=4) 

def upgrade_conf(conf):
    if conf['conf_version'] == 1:
        new_conf = {'channels':{}, 'servers':{}, 'conf_version':2}
        for chan, cconf in conf['channels'].iteritems():
            new_conf['channels'][chan] = {}
            for name, addr in cconf.iteritems():
                new_conf['channels'][chan][name] = {'address':addr}
        for addr, sconf in conf['servers'].iteritems():
            sconf = deepcopy(sconf)
            ltinfo = [sconf.pop('last_phase_mode', None),
                      sconf.pop('last_turn', None),
                      sconf.pop('last_phase', None)]
            if all(x is not None for x in ltinfo):
                sconf['last_turn_info'] = ltinfo
            if sconf.pop('set_by_admin', False):
                for cconf in new_conf['channels'].itervalues():
                    for csconf in cconf.itervalues():
                        if csconf['address'] != addr: continue
                        csconf['flags'] = ['set_by_admin']
            new_conf['servers'][addr] = sconf
        conf = new_conf
    if conf['conf_version'] != CONF_VERSION:
        raise ValueError('Invalid conf_version "%(conf_version)s"' % conf)
    return conf

@ab_link('HELP')
def h_help(bot, reply, args):
    reply('freeciv+', 'Connect a Freeciv server to an IRC channel.')
    reply('freeciv-', 'Disconnect a Freeciv server from an IRC channel.')
    reply('freeciv?', 'List the Freeciv servers connected to an IRC channel.')

@ab_link(('HELP', 'fc+'), ('HELP', 'freeciv+'))
def h_help_fc_p(bot, reply, args):
    reply('!freeciv+\2 or \2!fc+ '
          '[#CHANNEL] NAME HOST[:PORT] [USERNAME [PASSWORD]] [!...]',
        'Add the Freeciv server at HOST:PORT (or :%d) to #CHANNEL (or the current'
        ' channel), so that activity on the server is reported there, prefixed by'
        ' NAME, which must start with a letter or digit and contain no spaces or'
        ' colons or dots. The bot will log in using USERNAME (or "%s") and (if'
        ' given) PASSWORD, which may each be enclosed in double quotes. Further'
        ' commands may be given on the same line. See also: \2!help fc-\2,'
        ' \2!help fc?\2.'
        % (DEFAULT_PORT, bot.conf['nick']))

@ab_link('!fc+', '!freeciv+')
@util.further
def h_fc_p(bot, id, target, args, full_msg, cont):
    try:
        lchan, cchan, args = cmd_chan('+', bot, id, target, args, need_op=True)
        match = re.match(
            r'(?P<name>\S+)\s+(?P<host>\S+?)(:(?P<port>\d+))?\s*'
            r'(\s+(?P<uname>\S*|".*?")(\s+(?P<pword>\S*|".*?"))?)?\s*'
            r'(?P<debug>debug)?\s*$', args)
        if not match: raise UserError(
            'Error: invalid syntax. See \2!help fc+\2 for correct usage.')
        name = match.group('name')
        host = match.group('host')
        port = int(match.group('port')) if match.group('port') else DEFAULT_PORT
        uname = match.group('uname')
        pword = match.group('pword')
        debug = bool(match.group('debug'))
        if uname and '"%s"' % uname[1:-1] == uname: uname = uname[1:-1]
        if pword and '"%s"' % pword[1:-1] == pword: pword = pword[1:-1]

        is_admin = yield auth.check(bot, id)
        cconf = conf['channels'].get(lchan, {})
        address = '%s:%d' % (host.lower(), port)
        sconf = conf['servers'].get(address, {})

        if not re.match(r'[^\W_][^:\.]*$', name.decode('utf8'), flags=re.U):
            raise UserError('The server name must start with a letter or digit'
                ' and contain no colons or dots.')
        if any(name.lower() == oname.lower() for oname in cconf.iterkeys()):
            raise UserError(
                'A server named "%s" already exists in %s.' % (name, cchan))
        if any(csconf['address'] == address for csconf in cconf.itervalues()):
            raise UserError('The server at %s is already linked to %s as "%s".'
                % (cchan, address, next(
                k for k in cconf.iterkeys() if cconf[k]['address'] == address)))
        if sconf and (sconf['username'], sconf['password']) == (uname, pword):
            raise UserError('The server at %s is already configured in another'
                ' channel with a different username or password. You must use'
                ' the same credentials, or contact a bot administrator for'
                ' further assistance.' % address)
        if not is_admin and url.is_global_address(host): raise UserError(
            '"%s" does not refer to a public internet host. Only a bot'
            ' administrator may link servers using such addresses.'% host)
        if uname is not None and len(uname) >= MAX_LEN_USERNAME: raise UserError(
            'The username must be shorter than %d bytes.' % MAX_LEN_USERNAME)
        if pword is not None and len(pword) >= MAX_LEN_PASSWORD: raise UserError(
            'The password must be shorter than %d bytes.' % MAX_LEN_PASSWORD)
        if len(cconf) >= MAX_CHAN_SERVERS: raise UserError(
            'No more than %d servers may be added to a channel.'
            % MAX_CHAN_SERVERS)
        if not is_admin and debug: raise UserError(
            'The "debug" flag may only be used by bot administrators.')

        cconf[name] = {'address': address}
        if is_admin: cconf[name]['flags'] = ['set_by_admin']
        if debug: cconf[name]['flags'].append('debug')
        conf['channels'][lchan] = cconf
        sconf['username'] = uname
        sconf['password'] = pword
        conf['servers'][address] = sconf
        save_conf()

        if address in connections:
            connections[address].freeciv_state.debug |= debug
        else:
            connect(bot, address, sconf)
        reply(bot, id, target, 'Added.')
        yield cont
    except Exception as e:
        reply(bot, id, target, 'Error: %s' % e)
        if not isinstance(e, UserError): raise

@ab_link(('HELP', 'fc-'), ('HELP', 'freeciv-'))
def h_help_fc_p(bot, reply, args):
    reply('!fc- [#CHANNEL] NAME1[ NAME2[ ...]] [!...]',
        'Remove the Freeciv servers identified by NAME1, NAME2, etc, from'
        ' #CHANNEL (or from the current channel). Further commands may be given'
        ' on the same line. See also: \2!help fc+\2, \2!help fc?\2.')

@ab_link('!fc-', '!freeciv-')
@util.further
def h_fc_m(bot, id, target, args, full_msg, cont):
    try:
        lchan, cchan, args = cmd_chan('-', bot, id, target, args, need_op=True)
        names = args.split()
        if not names: raise UserError(
            'Invalid syntax. See \2!help fc-\2 for correct usage.')
        cconf = conf['channels'].get(lchan, {}).copy()
        daddrs = []
        for name in list(names):
            for cname in cconf.keys():
                if name.lower() != cname.lower(): continue
                names.remove(name)
                daddrs.append(cconf.pop(cname)['address'])
        if names: raise UserError('The server%(srv)s not exist in %(chn)s.' % {
            'srv': (' "%s" does' % names[0]) if len(names) == 1 else
                   ('s "%s" and "%s" do' % ('", "'.join(names[:-1]), names[-1])),
            'chn': cchan})
        if cconf:
            conf['channels'][lchan] = cconf
        else:
            del conf['channels'][lchan]

        for address in daddrs:
            any_chan, debug = False, False
            for scconf in chain(*(c.values() for c in conf['channels'].values())):
                if scconf['address'] == address:
                    debug |= 'debug' in scconf['flags']
                    any_chan = True
            if not any_chan:
                del conf['servers'][address]
                if address in connections: disconnect(connections.pop(address))
            elif address in connections:
                connections[address].freeciv_state.debug = debug

        save_conf()
        reply(bot, id, target, 'Removed.')
        yield cont
    except Exception as e:
        reply(bot, id, target, 'Error: %s' % e)
        if not isinstance(e, UserError): raise

@ab_link(('HELP', 'fc?'), ('HELP', 'freeciv?'))
def h_help_fc_p(bot, reply, args):
    reply('!fc? [#CHANNEL]',
        'List the Freeciv servers connected to #CHANNEL (or the current channel).'
        ' See also: \2!help fc+\2, \2!help fc-\2.')


@ab_link('!fc?', '!freeciv?')
def h_fc_q(bot, id, target, args, full_msg):
    try:
        lchan, cchan, args = cmd_chan('?', bot, id, target, args, need_op=False)
        cconf = conf['channels'].get(lchan, {})
        if args.split(): raise UserError(
            'Invalid syntax. See \2!help fc?\2 for correct usage.')
        if not cconf: return reply(bot, id, target,
            'There are no Freeciv servers linked to %s.' % cchan, prefix=False)
        def rows():
            yield '\2Name', 'Address', 'Username', 'Password', 'Flags', 'Status\2'
            for name, csconf in sorted(cconf.iteritems()):
                address = csconf['address']
                sconf = conf['servers'][address]
                username, password = sconf['username'], sconf['password']
                username = '(default)' if username is None else username
                password = '(none)' if password is None else '*'*len(password)

                flags = ''.join(sorted({'set_by_admin': 'A', 'debug': 'D'}[f]
                                       for f in csconf.get('flags', [])))

                status = server_status_line(address)
                yield name, address, username, password, flags, status
        lenf = lambda s: len(s.replace('\2', ''))
        for line in chain(util.join_rows(*rows(), lenf=lenf), ('\2End of List\2',)):
            reply(bot, id, target, line, prefix=False)
    except Exception as e:
        reply(bot, id, target, 'Error: %s' % e)
        if not isinstance(e, UserError): raise

def cmd_chan(cmd_suf, bot, id, target, args, need_op):
    match = re.match(r'(?P<chan>#\S+)\s*(?P<args>.*)$', args)
    chan, args = match.group('chan', 'args') if match else (target, args)
    if not chan: raise UserError(
        'When using this command by PM, you must specify the channel'
        ' name. See \2!help fc%s\2.' % cmd_suf)
    lchan = chan.lower()
    cchan = channel.capitalisation.get(lchan, chan)
    if bot.nick.lower() not in map(str.lower, channel.track_channels[lchan]):
        raise UserError('To use this command, this bot must be in %s.%s' 
            % (cchan, '' if 'invite' not in sys.modules or bot not in
            sys.modules['invite'].link.installed_modes else (' You may cause it'
            ' to join using \2/invite %s %s\2.'% (bot.nick, cchan))))
    if need_op and not channel.has_op_in(bot, id.nick, chan): raise UserError(
        'You must be an operator in %s to use this command.' % cchan)
    return lchan, cchan, args

def update_phase(state):
    sconf = conf['servers'][state.name]
    turn_info = get_turn_info(state)
    if sconf.get('last_turn_info') != list(turn_info):
        sconf['last_turn_info'] = list(turn_info)
        sconf['last_notify_time'] = None
        sconf.pop('last_individual_notify_time', None)
        if not all(p['ai'] for p in players_to_move(state, turn_info)):
            chans = [c for (c,_) in linked_channels(state.name)]
            report_server_status([state.name], chans)
        save_conf()

@fc_link('FC_LOOP')
def h_fc_loop():
    while ab_link.installed_modes:
        bot, = ab_link.installed_modes
        now = time.time()

        for addr, sconf in conf['servers'].iteritems():
            if addr in connections:
                state = connections[addr].freeciv_state

                # Terminate timed-out connections.
                if state.last_recv_time is not None \
                and state.last_recv_time + RECV_TIMEOUT_S < now:
                    yield sign('FC_CONN_ERR', state, 'timed out.')
                    continue

                if state.stage < STAGE_LOADED: continue

                # Notify users of their turns in games.
                lntime = sconf.get('last_notify_time')
                if lntime is None or lntime + TURN_NOTIFY_INTERVAL_S <= now:
                    for chan, cconf in conf['channels'].iteritems():
                        for csname, csconf in cconf.iteritems():
                            if csconf['address'] != addr: continue
                            nicks = list(channel.track_channels[chan])
                            yield notify_users(
                                bot, chan, nicks, addr, csname, individual=False)

            else:
                # Reconnect to disconnected servers.
                retries = sconf.get('connect_retries', 0)
                error_time = sconf.get('last_error_time')
                delay = min(MAX_RECONNECT_DELAY_S,
                            MIN_RECONNECT_DELAY_S*(retries + 1))
                if error_time is None or time.time() >= error_time + delay:
                    connect(bot, addr, sconf)

        yield runtime.sleep(FC_LOOP_INTERVAL_S)

@ab_link('!turn', '!freeciv', '!fc')
def h_turn(bot, id, target, args, full_msg):
    if target is not None:
        cconf = conf['channels'].get(target.lower(), {})
        report_server_status([s['address'] for s in cconf.itervalues()], [target])

@ab_link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    for csname, csconf in conf['channels'].get(chan.lower(), {}).iteritems():
        if csconf['address'] not in connections: continue
        yield notify_users(bot,
            chan, [id.nick], csconf['address'], csname, individual=True)

@util.mmsub(ab_link, 'freeciv.notify_users')
def notify_users(bot, chan, nicks, addr, dname, individual):
    state = connections[addr].freeciv_state
    turn_info = get_turn_info(state)
    sconf = conf['servers'][addr]
    now = time.time()

    notify_nicks, notify_usernames = set(), set()
    to_move = players_to_move(state, turn_info)
    for player_info in to_move:
        name = player_name(state, player_info['playerno'])
        for nick in list(nicks):
            if nick.lower() != name.lower():
                access = yield identity.check_access(bot, nick, name)
                if not access: continue
            nicks.remove(nick)
            notify_nicks.add(nick)
            notify_usernames.add(player_info['username'])

    if notify_nicks:
        lint = sconf.get('last_individual_notify_time', {})
        if individual and all(lint.get(u) is not None
        and lint[u] + INDIVIDUAL_TURN_NOTIFY_INTERVAL_S > now
        for u in notify_usernames):
            return

        notify_nicks_str = ', '.join(sorted(notify_nicks))
        if turn_info.phase_mode == PHASE_MODE.PLAYERS_ALTERNATE \
        or turn_info.phase_mode == PHASE_MODE.TEAMS_ALTERNATE \
        and len(players_on_team(state, player_info['team'])) == 1:
            bot.send_msg(chan, '%s: it is your turn in the Freeciv game "%s".'
                % (notify_nicks_str, dname))
        else:
            bot.send_msg(chan, '%s: the Freeciv game "%s" awaits your move.'
                % (notify_nicks_str, dname))

        lint.update({username:now for username in notify_usernames})
        sconf['last_individual_notify_time'] = lint
        if individual:
            sconf['last_notify_time'] = max(
                sconf.get('last_notify_time'),
                min(lint.get(p['username']) for p in to_move))
            save_conf()

    if not individual:
        sconf['last_notify_time'] = now
        save_conf()

def report_server_status(addrs, chans):
    bot, = ab_link.installed_modes
    for addr in addrs:
        tinfo = None
        if addr in connections:
            state = connections[addr].freeciv_state
            if state.stage >= STAGE_LOADED: tinfo = get_turn_info(state)

        for chan in chans:
            dname = next(n for (n, s) in conf['channels'][chan.lower()].iteritems()
                         if s['address'] == addr)
            bot.send_msg(chan, '%s: %s' % (dname, server_status_line(addr, tinfo)))

        if tinfo is not None and tinfo.phase_mode == PHASE_MODE.PLAYERS_ALTERNATE \
        and player_name(state, tinfo.phase).lower() in \
        (n.lower() for c in chans for n in channel.track_channels[c.lower()]):
            now = time.time()
            uname = state.last_recv[PACKET_PLAYER_INFO, tinfo.phase]['username']
            conf['servers'][addr]['last_notify_time'] = now
            conf['servers'][addr]['last_individual_notify_time'] = {uname: now}

    save_conf()

def report(addr, msg):
    bot, = ab_link.installed_modes
    for chan, dname in linked_channels(addr):
        bot.send_msg(chan, '%s: %s' % (dname, msg))

def linked_channels(addr):
    for chan, cconf in conf['channels'].iteritems():
        for dname, csconf in cconf.iteritems():
            if csconf['address'] == addr: yield chan, dname

def server_status_line(address, turn_info=None):
    sconf = conf['servers'][address]
    retries = sconf.get('connect_retries', 0)
    if address not in connections or retries > 0:
        error_string = sconf.get('last_error') or 'unknown error'
        return '%s (%d attempt%s; %s).' % (
            'Reconnecting' if address in connections else
            'Connection failed' if retries > 0 else
            'Waiting to reconnect', retries, 's' if retries > 1 else '',
            error_string)
    else:
        state = connections[address].freeciv_state
        return 'Connecting...' if state.stage < STAGE_LOADED else \
               game_status_line(state, turn_info)

def game_status_line(state, turn_info=None):
    phase_mode, turn, phase = turn_info or get_turn_info(state)
    if phase in (PHASE_INVALIDATED, PHASE_UNKNOWN):
        return 'Turn %d, status unknown.' % turn
    elif phase_mode == PHASE_MODE.CONCURRENT:
        return 'Turn %d.' % turn
    elif phase_mode == PHASE_MODE.TEAMS_ALTERNATE:
        return 'Turn %d, %s team\'s turn.' % (turn, team_name(state, phase))
    elif phase_mode == PHASE_MODE.PLAYERS_ALTERNATE:
        return 'Turn %d, %s\'s turn.' % (turn, player_name(state, phase))
    else: assert False

# Returns a list of PACKET_PLAYER_INFO dicts.
def players_to_move(state, turn_info=None):
    if turn_info is None: turn_info = get_turn_info(state)
    return [
        p for (k, p) in state.last_recv.iteritems()
        if k[0] == PACKET_PLAYER_INFO and turn_info.phase == {
            PHASE_MODE.CONCURRENT: turn_info.phase,
            PHASE_MODE.TEAMS_ALTERNATE: p['team'],
            PHASE_MODE.PLAYERS_ALTERNATE: p['playerno'],
        }[turn_info.phase_mode]
        and not (p['ai'] or p['unassigned_user'] or p['phase_done'])]

# Returns a list of PACKET_PLAYER_INFO dicts.
def players_on_team(state, team_id):
    return [p for (k, p) in state.last_recv.iteritems()
            if k[0] == PACKET_PLAYER_INFO and p['team'] == team_id]

def get_turn_info(state):
    game_info = state.last_recv[PACKET_GAME_INFO,]
    new_year = state.last_recv.get((PACKET_NEW_YEAR,))
    start_phase = state.last_recv.get((PACKET_START_PHASE,))
    return TurnInfo(
        phase_mode = game_info['phase_mode'],
        turn       = (new_year    or game_info)['turn'],
        phase      = (start_phase or game_info)['phase'])

def player_name(state, playerno):
    player = state.last_recv[PACKET_PLAYER_INFO, playerno]
    return bridge.substitute_name(state.name, player['username']) \
           if not player['unassigned_user'] else \
          'P%d (%s)' % (player['playerno'], player['name'])

def team_name(state, team_id):
    name_info = state.last_recv[PACKET_TEAM_NAME_INFO, team_id]
    return name_info['team_name'].replace('?team name:', '')

@fc_link(untwisted.event.RECV_ERR, untwisted.event.SEND_ERR, untwisted.event.CLOSE)
def h_recv_err_send_err_close(work, exc=None):
    state = work.freeciv_state
    if state.name not in connections: return
    yield sign('FC_CONN_ERR', state, exc)

@fc_link('FC_CONN_ERR')
def h_fc_conn_err(state, exc=None):
    if state.name in connections: connections.pop(state.name).destroy()
    sconf = conf['servers'][state.name]
    if state.stage < STAGE_ACCEPTED:
        msg = 'Failed to connect to server'
        sconf['connect_retries'] = sconf.get('connect_retries', 0) + 1
    else:
        msg = 'Disconnected from server'
    retries = sconf.get('connect_retries', 0)
    if retries <= 1:
        report(state.name, ('%s: %s' % (msg, exc)) if exc else ('%s.' % msg))
    sconf['last_error_time'] = time.time()
    sconf['last_error'] = str(exc) if exc is not None else None
    save_conf()

@fc_link(untwisted.event.BUFFER)
def h_buffer(work, data):
    state = work.freeciv_state
    while data:
        if state.chunk_rem:
            chunk, data = data[:state.chunk_rem], data[state.chunk_rem:]
            state.chunk_buf += state.decompress_obj.decompress(chunk)
            state.chunk_rem -= len(chunk)
            if state.chunk_rem: break
            state.chunk_buf += state.decompress_obj.flush()
            del state.decompress_obj

        if len(data) < 2: break
        length, = struct.unpack('!H', data[:2])
 
        if length > COMPRESSION_BORDER:
            if length == JUMBO_SIZE:
                if len(data) < 6: break
                state.chunk_rem = struct.unpack('!I', data[2:6])[0] - 6
                data = data[6:]
            else:
                state.chunk_rem = length - COMPRESSION_BORDER - 2
                data = data[2:]
            state.decompress_obj = zlib.decompressobj()
            continue

        state.chunk_buf += data[:length]
        data = data[length:]
    work.stack = data

    while len(state.chunk_buf) >= 2:
        length, = struct.unpack('!H', state.chunk_buf[:2])
        if len(state.chunk_buf) < length: break
        pdata, state.chunk_buf = state.chunk_buf[2:length], state.chunk_buf[length:]
        if work.freeciv_state.stage <= STAGE_INITIAL \
        or work.freeciv_state.version[:2] <= (2, 6):
            ptype, pdata = struct.unpack('!B', pdata[:1]) + (pdata[1:],)
        else:
            ptype, pdata = struct.unpack('!H', pdata[:2]) + (pdata[2:],)
        yield sign(('FC_RECV_PACKET_DATA', ptype), work, pdata)

@fc_link('FC_SEND_PACKET_DATA')
def h_fc_send_packet_data(work, packet_type, data):
    if work.freeciv_state.stage <= STAGE_INITIAL \
    or work.freeciv_state.version[:2] <= (2, 6):
        header = struct.pack('!HB', len(data) + 3, packet_type)
    else:
        header = struct.pack('!HH', len(data) + 4, packet_type)
    work.dump(header + data)

class Field(object):
    def __init__(self, name, field_type, key=False):
        self.name = name
        self.type = field_type() if isinstance(field_type, type) else field_type
        self.key = key

class FieldType(object):
    def delta_read(self, data, delta_bit, prev_value, *args, **kwds):
        if delta_bit:
            value, data = self.read(data)
            return value, True, data
        elif prev_value is None:
            return self.default(), False, data
        else:
            return prev_value, False, data
    def delta_write(self, value, prev_value, *args, **kwds):
        return ('', False, False) if value == prev_value else \
               (self.write(value), True, True)
    def array_typecode(self):
        return None
    def value_repr(self, value):
        return repr(value)
    def __eq__(self, other):
        return type(self) is type(other) and self.__dict__ == other.__dict__
    def __ne__(self, other):
        return type(self) is not type(other) or self.__dict__ != other.__dict__

class Array(FieldType):
    def __init__(self, el_type, *dimensions, **kwds):
        self.element_type = el_type() if isinstance(el_type, type) else el_type
        self.dimensions = dimensions
        self.diff = kwds.pop('diff', False)
        if self.diff:
            assert len(dimensions) == 1 and \
                   isinstance(dimensions[0], int) and \
                   dimensions[0] < 256
        assert not kwds

    def delta_read(self, data, delta_bit, prev_value, prev_fields):
        if delta_bit:
            value, data = self.read(data, prev_value, prev_fields)
            return value, True, data
        elif prev_value is None:
            return self.default(), False, data
        else:
            return prev_value, False, data

    def read(self, data, prev_value=None, prev_fields={}):
        if self.diff:
            value = self.default() if prev_value is None else deepcopy(prev_value)
            while data[0] != '\xFF':
                index, (element, data) = data[0], self.element_type.read(data[1:])
                value[ord(index)] = element
            return value, data[1:]

        dimensions = self.get_dimensions(prev_fields)
        typecode = self.element_type.array_typecode()
        if typecode is None:
            return self.read_list(data, dimensions)
        el_size = struct.calcsize(typecode)
        ar_size = reduce(operator.mul, dimensions)
        return util.md_array(typecode, dimensions, (
            self.element_type.read(data[el_size*i:el_size*(i+1)])[0]
            for i in xrange(ar_size))), data[el_size*ar_size:]

    def read_list(self, data, dimensions):
        if len(dimensions) == 0:
            return self.element_type.read(data)
        count, dimensions = dimensions[0], dimensions[1:]
        list = []
        for i in xrange(count):
            value, data = self.read_list(data, dimensions)
            list.append(value)
        return list, data

    def delta_write(self, value, prev_value, prev_fields):
        return ('', False, False) if value == prev_value else \
               (self.write(value, prev_value, prev_fields), True, True)

    def write(self, value, prev_value=None, prev_fields={}):
        dimensions = self.get_dimensions(prev_fields)
        output = StringIO()
        if self.diff:
            if prev_value is None: prev_value = self.default()
            for element, prev_element, index in izip(value, prev_value, count()):
                if element == prev_element: continue
                output.write(chr(index))
                output.write(self.element_type.write(element))
            output.write('\xFF')
        elif isinstance(value, util.md_array):
            assert value.dimensions == dimensions
            for element in value.array:
                output.write(self.element_type.write(element))
        else:
            self.write_list(value, output, dimensions)
        return output.getvalue()

    def write_list(self, items, output, dimensions):
        assert len(items) == dimensions[0]
        for item in items:
            if isinstance(item, list):
                self.write_list(item, output, dimensions[1:])
            else:
                output.write(self.element_type.write(item))

    def get_dimensions(self, prev_fields):
        return tuple(prev_fields[d] if isinstance(d, str) else d
                     for d in self.dimensions)

    def default(self):
        typecode = self.element_type.array_typecode()
        dimensions = self.get_dimensions(defaultdict(lambda: 0))
        if typecode is not None: return util.md_array(typecode, dimensions)
        return self.default_list(self.dimensions)

    def default_list(self, dimensions):
        if len(dimensions) == 0: return self.element_type.default()
        count, dimensions = dimensions[0], dimensions[1:]
        if isinstance(count, str): count = 0
        return [self.default_list(dimensions) for i in xrange(count)]

class Struct(FieldType):
    def __init__(self, format, multi=False):
        self.format = '!' + format
        self.multi = multi
    def read(self, data, *args, **kwds):
        size = struct.calcsize(self.format)
        value = struct.unpack(self.format, data[:size])
        if not self.multi: (value,) = value
        return value, data[size:]
    def write(self, value, *args, **kwds):
        if not self.multi: value = (value,)
        return struct.pack(self.format, *value)
    def array_typecode(self):
        return self.format[1:] if self.format[1:] in 'cbBuhHiIlLfd' else None
    def default(self):
        value = struct.unpack(self.format, '\0'*struct.calcsize(self.format))
        if not self.multi: (value,) = value
        return value

class Enum(Struct):
    def __init__(self, *members, **set_members):
        min_v, max_v = 0, 0
        self.members = dict(chain(izip(members, count()), set_members.iteritems()))
        for member, value in self.members.iteritems():
            setattr(self, member, value)
            min_v, max_v = min(min_v, value), max(max_v, value)
        assert 0 <= min_v and max_v <= 0xFFFFFFFF, (min_v, max_v)
        super(Enum, self).__init__(
            'B' if max_v <= 0xFF else 'H' if max_v <= 0xFFFF else 'I')

    def value_repr(self, value):
        for mname, mvalue in self.members.iteritems():
            if mvalue == value: return mname
        return super(Enum, self).value_repr(value)

class BitEnum(Enum):
    def __init__(self, *members, **set_members):
        members = {m: 1<<i for (m, i) in izip(members, count())}
        members.update(set_members)
        super(BitEnum, self).__init__(**members)

    def value_repr(self, value):
        elements = {}
        for mname, mvalue in self.members.iteritems():
            if value | mvalue != value: continue
            for ename, evalue in elements.items():
                if evalue | mvalue == evalue: continue
                if evalue | mvalue == mvalue: del elements[ename]
            elements[mname] = mvalue
        if not elements or reduce(operator.or_, elements.itervalues(), 0) != value:
            return super(BitEnum, self).value_repr(value)
        return '|'.join(sorted(elements.iterkeys()))

class BitVector(Struct):
    def __init__(self, nbits):
        self.nbits = nbits
        self.nbytes = -(-nbits/8)
        super(BitVector, self).__init__('%dB' % self.nbytes, multi=True)

    def write(self, bits, *args, **kwds):
        return super(BitVector, self).write(
            self.bytes_to_bits(bytes), *args, **kwds)

    def read(self, data, *args, **kwds):
        value, data = super(BitVector, self).read(data, *args, **kwds)
        return self.bytes_to_bits(value), data

    def default(self):
        return self.bytes_to_bits(super(BitVector, self).default())

    def bytes_to_bits(self, bytes):
        assert len(bytes) == self.nbytes, '%d != %d' % (len(bytes), self.nbytes)
        return [bool((bytes[i] >> j) & 1) for i in xrange(self.nbytes)
                for j in xrange(8) if 8*i+j < self.nbits]

    def bits_to_bytes(self, bits):
        assert len(bits) == self.nbits, '%d != %d' % (len(bits), self.nbits)
        return (sum(int(bits[8*i+j])<<j for j in xrange(8) if 8*i+j < self.nbits)
                for i in xrange(self.nbytes))

class Bool(Struct):
    def __init__(self):
        super(Bool, self).__init__('?')
    def delta_read(self, data, delta_bit, prev_value, *args, **kwds):
        return delta_bit, delta_bit != prev_value, data
    def delta_write(self, value, *args, **kwds):
        return '', True, value
    def default(self):
        return False
    def array_typecode(self):
        return 'B'

class String(FieldType):
    def __init__(self, max_length):
        self.max_length = max_length
    def read(self, data, *args, **kwds):
        end = data.find('\0')
        assert end < self.max_length, 'len(%r) = %d >= %d' % (
            data[:end], end, self.max_length)
        return data[:end], data[end+1:]
    def write(self, value, *args, **kwds):
        if type(value) is unicode: value = value.encode('utf8')
        assert len(value) < self.max_length and '\0' not in value
        return value + '\0'
    def default(self):
        return ''

class Packet(object):
    def __init__(self, name, number, *fields, **kwds):
        self.name = name
        self.number = number
        self.fields = fields
        self.delta = kwds.pop('delta', True)
        self.cancel = kwds.pop('cancel', ())
        assert not kwds

    def read(self, data, prev_packets, debug=False):
        if debug: print('**> %s' % self.name)
        packet = {}
        key = (self.number,)
        if self.delta:
            delta_bits, data = self.read_delta_header(data)
            for field in self.fields:
                if field.key:
                    packet[field.name], data = field.type.read(data, packet)
                    key += (packet[field.name],)
                    present = True
                else:
                    prev_value = prev_packets[key][field.name] \
                                 if key in prev_packets else None
                    packet[field.name], present, data = field.type.delta_read(
                        data, delta_bits.pop(0), prev_value, packet)
                if present and debug:
                    value_repr = field.type.value_repr(packet[field.name])
                    print('    | %s = %s' % (field.name, value_repr))
        else:
            for field in self.fields:
                packet[field.name], data = field.type.read(data, packet)
                if field.key: key += (packet[field.name],)
                if debug:
                    value_repr = field.type.value_repr(packet[field.name])
                    print('    | %s = %s' % (field.name, value_repr))

        self.update_prev_packets(prev_packets, key, packet)
        return packet, data

    def read_delta_header(self, data):
        nbits = sum(1 for f in self.fields if not f.key)
        nbytes = -(-nbits/8)
        bits = [bool((ord(data[i/8]) >> (i%8)) & 1) for i in xrange(nbits)]
        return bits, data[nbytes:]

    def write(self, field_values, prev_packets, debug=False):
        if debug: print('<** %s' % self.name)
        data = StringIO()
        key = (self.number,)
        if self.delta:
            delta_header = []
            for field in self.fields:
                field_value = field_values[field.name]
                if field.key:
                    present, field_data = field.type.write(field_value, field_values)
                    key += (field_value,)
                else:
                    prev_value = prev_packets[key][field.name] \
                                 if key in prev_packets else None
                    field_data, present, delta_bit = \
                        field.type.delta_write(field_value, prev_value)
                    delta_header.append(delta_bit)
                data.write(field_data)
                if present and debug:
                    value_repr = field.type.value_repr(field_values[field.name])
                    print('    | %s = %s' % (field.name, value_repr))
            nbits = len(delta_header)
            nbytes = -(-nbits/8)
            delta_header = ''.join(chr(sum(int(delta_header[8*i + j]) << j
                for j in xrange(8) if 8*i + j < nbits)) for i in xrange(nbytes))
            data = delta_header + data.getvalue()
        else:
            for field in self.fields:
                if field.key: key += (field_values[field.name],)
                field_data = field.type.write(field_values[field.name], field_values)
                data.write(field_data)
                if debug:
                    value_repr = field.type.value_repr(field_values[field.name])
                    print('    | %s = %s' % (field.name, value_repr))
            data = data.getvalue()

        self.update_prev_packets(prev_packets, key, field_values)
        return data

    def update_prev_packets(self, prev_packets, key, packet):
        prev_packets[key] = packet
        for cnumber in self.cancel:
            ckey = (cnumber,)
            for field, cfield in izip(self.fields, PACKETS[cnumber].fields):
                if not cfield.key: continue
                assert field.type == cfield.type
                ckey += (packet[field.name],)
            prev_packets.pop(ckey, None)

def fc_recv(packet):
    @fc_link(('FC_RECV_PACKET_DATA', packet.number))
    def h_fc_recv_packet_data(work, data):
        field_values, data = packet.read(data, work.freeciv_state.last_recv,
            debug=work.freeciv_state.debug)
        assert not data, repr(data)
        work.freeciv_state.last_recv_time = time.time()
        yield sign(('FC_RECV', packet.number), work, **field_values)
    globals()['PACKET_'+packet.name] = packet.number
    PACKETS[packet.number] = packet

def fc_send(packet):
    @fc_link(('FC_SEND', packet.number))
    def h_fc_send(work, **field_values):
        data = packet.write(field_values, work.freeciv_state.last_send,
            debug=work.freeciv_state.debug)
        yield sign('FC_SEND_PACKET_DATA', work, packet.number, data)
    globals()['PACKET_' + packet.name] = packet.number
    PACKETS[packet.number] = packet

UINT8, SINT8, UINT16, SINT16, UINT32, SINT32 = map(Struct, 'BbHhIi')

CITYSPE    = SINT32
CONNECTION = SINT16
GOLD       = UINT32
GOVERNMENT = SINT8  # Government_type_id
NATION     = SINT16 # Nation_type_id
PERCENT    = UINT8
PHASE      = SINT16
PLAYER     = UINT8
TEAM       = UINT8
TURN       = SINT16
YEAR       = SINT16

BV_PLAYER = BitVector(MAX_NUM_PLAYER_SLOTS)

AIRLIFTING_STYLE   = BitEnum('ALLIED_SRC', 'ALLIED_DEST', 'UNLIM_SRC', 'UNLIM_DEST')
AUTH_TYPE          = BitEnum('NEWUSER', 'RETRY')
BARBARIAN_TYPE     = Enum('NONE', 'LAND', 'SEA', 'ANIMAL')
BORDERS_MODE       = Enum('DISABLED', 'ENABLED', 'SEE_INSIDE', 'EXPAND')
CMDLEVEL           = Enum('NONE', 'INFO', 'BASIC', 'CTRL', 'ADMIN', 'HACK', 'COUNT')
DIPLOMACY_MODE     = Enum('ALL', 'HUMAN', 'AI', 'NO_MIXED', 'TEAMS', 'DISABLED')
FTM                = Enum('GOAL', 'RANDOM', 'CHEAPEST') # free_tech_method
GLS                = BitEnum('BARB', 'CWAR', 'LOOT')
GOLD_UPKEEP_STYLE  = Enum('CITY', 'MIXED', 'NATION')
HAPPYBORDERSTYPE   = Enum('DISABLED', 'NATIONAL', 'ALLIANCE')
MOOD               = Enum('PEACEFUL', 'COMBAT', 'COUNT')
OUTPUT_TYPE    = Enum('FOOD', 'SHIELD', 'TRADE', 'GOLD', 'LUXURY', 'SCIENCE', 'LAST')
PERSISTENT_READY   = Enum('DISABLED', 'CONNECTED')
PHASE_MODE         = Enum('CONCURRENT', 'PLAYERS_ALTERNATE', 'TEAMS_ALTERNATE')
REVOLENTYPE        = Enum('FIXED', 'RANDOM', 'QUICKENING', 'RANDQUICK')
TECH_COST_STYLE    = Enum('CIV1_2', 'CLASSIC', 'CLASSIC_PRE', 'EXPERI', 'EXPERI_PRE')
TECH_LEAKAGE_STYLE = Enum('NONE', 'EMBASSIES', 'PLAYERS', 'NO_BARBS')
TECH_UPKEEP_STYLE  = Enum('NONE', 'BASIC', 'PER_CITY')
VICTORY_CONDITIONS = Enum('SPACERACE', 'ALLIED', 'CULTURE')

fc_recv(Packet('PROCESSING_STARTED', 0))

fc_recv(Packet('PROCESSING_FINISHED', 1))

fc_send(Packet('SERVER_JOIN_REQ', 4,
    Field('username', String(MAX_LEN_USERNAME)),
    Field('capability', String(512)),
    Field('version_label', String(48)),
    Field('major_version', UINT32),
    Field('minor_version', UINT32),
    Field('patch_version', UINT32),
delta=False))

fc_recv(Packet('SERVER_JOIN_REPLY', 5,
    Field('you_can_join', Bool),
    Field('message', String(1536)),
    Field('capability', String(512)),
    Field('challenge_file', String(4095)),
    Field('conn_id', CONNECTION),
delta=False))

fc_recv(Packet('AUTHENTICATION_REQ', 6,
    Field('auth_type', AUTH_TYPE),
    Field('message', String(MAX_LEN_MSG)),
))

fc_send(Packet('AUTHENTICATION_REPLY', 7,
    Field('password', String(MAX_LEN_PASSWORD)),
))

fc_recv(Packet('TEAM_NAME_INFO', 19,
    Field('team_id', TEAM, key=True),
    Field('team_name', String(MAX_LEN_NAME)),
))

fc_recv(Packet('GAME_INFO', 16,
    Field('add_to_size_limit', UINT8),
    Field('aifill', UINT8),
    Field('persistent_ready', PERSISTENT_READY),
    Field('airlifting_style', AIRLIFTING_STYLE),
    Field('angrycitizen', UINT8),
    Field('base_pollution', SINT16),
    Field('base_tech_cost', UINT8),
    Field('border_city_radius_sq', UINT16),
    Field('border_size_effect', UINT8),
    Field('border_city_permanent_radius_sq', SINT16),
    Field('borders', BORDERS_MODE),
    Field('base_bribe_cost', UINT32),
    Field('culture_vic_points', UINT32),
    Field('culture_vic_lead', UINT16),
    Field('culture_migration_pml', UINT16),
    Field('calendar_skip_0', Bool),
    Field('celebratesize', UINT8),
    Field('changable_tax', Bool),
    Field('pop_report_zeroes', UINT8),
    Field('citizen_nationality', Bool),
    Field('citizen_convert_speed', UINT16),
    Field('citizen_partisans_pct', UINT8),
    Field('citymindist', UINT8),
    Field('cooling', UINT32),
    Field('coolinglevel', UINT32),
    Field('diplomacy', DIPLOMACY_MODE),
    Field('fogofwar', Bool),
    Field('food_cost', UINT8),
    Field('foodbox', UINT32),
    Field('forced_gold', UINT8),
    Field('forced_luxury', UINT8),
    Field('forced_science', UINT8),
    Field('fulltradesize', UINT8),
    Field('global_advances', Array(Bool, A_LAST, diff=True)),
    Field('global_warming', Bool),
    Field('globalwarming', UINT32),
    Field('gold', GOLD),
    Field('gold_upkeep_style', GOLD_UPKEEP_STYLE),
    Field('revolentype', REVOLENTYPE),
    Field('default_government_id', GOVERNMENT),
    Field('government_during_revolution_id', GOVERNMENT),
    Field('granary_food_inc', UINT8),
    Field('granary_food_ini', Array(UINT8, MAX_GRANARY_INIS)),
    Field('granary_num_inis', UINT8),
    Field('great_wonder_owners', Array(PLAYER, B_LAST, diff=True)),
    Field('happy_cost', UINT8),
    Field('happyborders', HAPPYBORDERSTYPE),
    Field('heating', UINT32),
    Field('illness_base_factor', UINT16),
    Field('illness_min_size', UINT8),
    Field('illness_on', Bool),
    Field('illness_pollution_factor', UINT16),
    Field('illness_trade_infection', UINT16),
    Field('init_city_radius_sq', UINT8),
    Field('is_edit_mode', Bool),
    Field('is_new_game', Bool),
    Field('killcitizen', Bool),
    Field('killstack', Bool),
    Field('min_city_center_output', Array(UINT8, OUTPUT_TYPE.LAST)),
    Field('negative_year_label', String(MAX_LEN_NAME)),
    Field('notradesize', UINT8),
    Field('nuclear_winter', Bool),
    Field('nuclearwinter', UINT32),
    Field('phase', PHASE),
    Field('phase_mode', PHASE_MODE),
    Field('pillage_select', Bool),
    Field('tech_steal_allow_holes', Bool),
    Field('tech_trade_allow_holes', Bool),
    Field('tech_trade_loss_allow_holes', Bool),
    Field('tech_parasite_allow_holes', Bool),
    Field('tech_loss_allow_holes', Bool),
    Field('positive_year_label', String(MAX_LEN_NAME)),
    Field('rapturedelay', UINT8),
    Field('disasters', UINT16),
    Field('restrictinfra', Bool),
    Field('unreachable_protects', Bool),
    Field('sciencebox', UINT32),
    Field('shieldbox', UINT32),
    Field('skill_level', UINT32),
    Field('slow_invasions', Bool),
    Field('victory_conditions', VICTORY_CONDITIONS),
    Field('team_pooled_research', Bool),
    Field('tech', UINT32),
    Field('tech_cost_style', TECH_COST_STYLE),
    Field('tech_leakage', TECH_LEAKAGE_STYLE),
    Field('tech_upkeep_divider', UINT16),
    Field('tech_upkeep_style', TECH_UPKEEP_STYLE),
    Field('techloss_forgiveness', SINT16),
    Field('free_tech_method', FTM),
    Field('gameloss_style', GLS),
    Field('timeout', UINT32),
    Field('first_timeout', UINT32),
    Field('tired_attack', Bool),
    Field('trademindist', UINT16),
    Field('force_trade_route', Bool),
    Field('trading_city', Bool),
    Field('trading_gold', Bool),
    Field('trading_tech', Bool),
    Field('turn', TURN),
    Field('warminglevel', UINT32),
    Field('year', YEAR),
    Field('year_0_hack', Bool),
    Field('calendar_fragments', UINT16),
    Field('fragment_count', UINT16),
    Field('calendar_fragment_name',
        Array(String(MAX_LEN_NAME), MAX_CALENDAR_FRAGMENTS)),
    Field('civil_war_enabled', Bool),
    Field('paradrop_to_transport', Bool),
))

fc_send(Packet('CHAT_MSG_REQUEST', 26,
    Field('message', String(MAX_LEN_MSG)),
))

fc_recv(Packet('PLAYER_INFO', 51,
    Field('playerno', PLAYER, key=True),
    Field('name', String(MAX_LEN_NAME)),
    Field('username', String(MAX_LEN_NAME)),
    Field('unassigned_user', Bool),
    Field('score', UINT32),
    Field('is_male', Bool),
    Field('was_created', Bool),
    Field('government', GOVERNMENT),
    Field('target_government', GOVERNMENT),
    Field('real_embassy', Array(Bool, MAX_NUM_PLAYER_SLOTS)),
    Field('mood', MOOD ),
    Field('style', UINT8),
    Field('music_style', SINT8),
    Field('nation', NATION),
    Field('team', TEAM),
    Field('is_ready', Bool),
    Field('phase_done', Bool),
    Field('nturns_idle', TURN),
    Field('turns_alive', TURN),
    Field('is_alive', Bool),
    Field('gold', GOLD),
    Field('tax', PERCENT),
    Field('science', PERCENT),
    Field('luxury', PERCENT),
    Field('tech_upkeep', UINT16),
    Field('science_cost', UINT16),
    Field('is_connected', Bool),
    Field('revolution_finishes', TURN),
    Field('ai', Bool),
    Field('ai_skill_level', UINT8),
    Field('barbarian_type', BARBARIAN_TYPE),
    Field('gives_shared_vision', BV_PLAYER),
    Field('culture', UINT16),
    Field('love', Array(SINT16, MAX_NUM_PLAYER_SLOTS)),
    Field('color_valid', Bool),
    Field('color_changeable', Bool),
    Field('color_red', UINT8),
    Field('color_green', UINT8),
    Field('color_blue', UINT8),
    Field('wonders', Array(CITYSPE, B_LAST, diff=True)),
    Field('multip_count', UINT8),
    Field('multiplier', Array(SINT32, 'multip_count')),
    Field('multiplier_target', Array(SINT32, 'multip_count')),
))

fc_send(Packet('PLAYER_REMOVE', 50,
    Field('playerno', PLAYER),
cancel=(PACKET_PLAYER_INFO,)))

fc_recv(Packet('CONN_PING', 88))

fc_send(Packet('CONN_PONG', 89))

fc_recv(Packet('CONN_INFO', 115,
    Field('id', CONNECTION, key=True),
    Field('used', Bool),
    Field('established', Bool),
    Field('observer', Bool),
    Field('player_num', PLAYER),
    Field('access_level', CMDLEVEL),
    Field('username', String(MAX_LEN_NAME)),
    Field('addr', String(MAX_LEN_ADDR)),
    Field('capability', String(MAX_LEN_CAPSTR)),
))

fc_recv(Packet('START_PHASE', 126,
    Field('phase', PHASE),
))

fc_recv(Packet('NEW_YEAR', 127,
    Field('year', YEAR),
    Field('fragments', UINT16),
    Field('turn', TURN),
))

@fc_link(('FC_RECV', PACKET_AUTHENTICATION_REQ))
def h_authentication_req(work, auth_type, message):
    try:
        if not auth_type & AUTH_TYPE.RETRY == 0:
            raise UserError('Error: %s' % message)
        if work.freeciv_state.password is None:
            raise UserError('Error: No password configured: %s' % message)
        yield sign(('FC_SEND', PACKET_AUTHENTICATION_REPLY), work,
            password = work.freeciv_state.password)
        work.freeciv_state.password = None
    except UserError as e:
        yield sign('FC_CONN_ERR', work.freeciv_state, e)

@fc_link(('FC_RECV', PACKET_SERVER_JOIN_REPLY))
def h_server_join_reply(work,
    you_can_join, message, capability, challenge_file, conn_id
):
    try:
        if not you_can_join: raise UserError('Error: %s' % message)
        work.freeciv_state.stage = STAGE_ACCEPTED
        work.freeciv_state.conn_id = conn_id
        conf['servers'][work.freeciv_state.name].pop('last_error', None)
        conf['servers'][work.freeciv_state.name].pop('last_error_time', None)
        conf['servers'][work.freeciv_state.name].pop('connect_retries', None)
        report(work.freeciv_state.name, 'Connected to server.')
        yield sign(('FC_SEND', PACKET_CHAT_MSG_REQUEST), work, message='/detach')
    except UserError as e:
        yield sign('FC_CONN_ERR', work.freeciv_state, e)

@fc_link(('FC_RECV', PACKET_PROCESSING_FINISHED))
def h_processing_finished(work):
    if work.freeciv_state.stage == STAGE_ACCEPTED:
        work.freeciv_state.stage = STAGE_LOADED
        update_phase(work.freeciv_state)

@fc_link(('FC_RECV', PACKET_START_PHASE))
def h_start_phase(work, phase):
    if work.freeciv_state.stage >= STAGE_LOADED:
        update_phase(work.freeciv_state)

@fc_link(('FC_RECV', PACKET_CONN_PING))
def h_conn_ping(work):
    yield sign(('FC_SEND', PACKET_CONN_PONG), work)
