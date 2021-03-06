#==============================================================================#
import util
import runtime
import terraria_protocol
import bridge

from untwisted.magic import sign
from untwisted.usual import Stop
import untwisted.event
import untwisted.mode
import untwisted.network

from datetime import datetime
import traceback
import socket
import json
import sys
import re
import operator

#==============================================================================#
RECONNECT_DELAY_SECONDS = 30
VERSION_RECONNECT_DELAY_SECONDS = 5
MAX_CHAT_LENGTH = 127
STATE_FILE = 'state/terraria.json'

IGNORE_MESSAGES=(
    'The air is getting colder around you...',
    'You feel vibrations from deep below...',
    'This is going to be a terrible night...',
    'A solar eclipse is happening!',
    re.compile(r'.* the Travell?ing Merchant has (arrived|departed)!$'),
    re.compile(r'Looks like .* (is|are) throwing a party$'),
    "Party time's over!",
    'Slime is falling from the sky!',
    'Slime has stopped falling from the sky.',
    re.compile(r'.* was slain\.\.\.'))

servers = util.table('conf/terraria.py', 'server')

te_mode = untwisted.mode.Mode()
te_link = util.LinkSet()
te_link.link_module(terraria_protocol, debug=False)
te_work = dict()

ab_mode = None
ab_link = util.LinkSet()

#==============================================================================#
def get_state():
    try:
        with open(STATE_FILE) as file:
            return util.recursive_encode(json.load(file), 'utf-8')
    except (ValueError, IOError):
        return dict()

def put_state(state):
    data = json.dumps(state, indent=4, ensure_ascii=False)
    with open(STATE_FILE, 'w') as file:
        file.write(data)

#==============================================================================#
def install(bot):
    global ab_mode, te_work
    if ab_mode is not None: raise util.AlreadyInstalled
    ab_mode = bot
    ab_link.install(ab_mode)
    te_link.install(te_mode)

    prev_work, te_work = te_work, dict()
    for work in prev_work.itervalues():
        try: reload_work(work)
        except NameError: traceback.print_exc()

    for server in servers:
        if server.name.lower() not in te_work:
            te_work[server.name.lower()] = init_work(server)

def reload_uninstall(bot):
    uninstall(bot, reload=True)

def uninstall(bot, reload=False):
    global ab_mode
    if ab_mode is None: raise util.NotInstalled
    if not reload:
        for work in te_work.itervalues(): kill_work(work)
    te_link.uninstall(te_mode)
    ab_link.uninstall(ab_mode)
    ab_mode = None

def reload(prev):
    if not hasattr(prev, 'te_work'): return
    if not isinstance(prev.te_work, dict): return
    te_work.update(prev.te_work)

#==============================================================================#
def reload_work(work):
    match = [s for s in servers if s.name.lower() not in te_work
             and s.address == work.terraria.address
             and s.user == work.terraria.user]
    if match:
        te_work[match[0].name.lower()] = init_work(match[0], work)
    else:
        if (hasattr(work, 'terraria_protocol')
        and work.terraria_protocol.stage >= 3):
            msg = 'Disconnected from server: configuration update.'
            te_mode.drive('TERRARIA', work, msg)
        kill_work(work)

#-------------------------------------------------------------------------------
def init_work(server, reload_from=None, reconnect_from=None, version=None):
    if reload_from is not None:
        reload_from.destroy()
        work = untwisted.network.Work(te_mode, reload_from.sock)
        if hasattr(reload_from, 'terraria_protocol'):
            work.terraria_protocol = reload_from.terraria_protocol
        work.prev_terraria_protocol = getattr(
            reload_from, 'prev_terraria_protocol', None)
        if (hasattr(work, 'terraria_protocol')
        and work.terraria_protocol.stage >= 3):
            te_mode.drive('HEARTBEAT', work)
    else:
        if version is None:
            state = get_state().get(repr(server.address), dict())
            version = state.get('version')
        work = untwisted.network.Work(te_mode, socket.socket())
        work.setblocking(0)
        work.connect_ex(server.address)
        terraria_protocol.login(
            work, server.user, server.password, version=version)
        if hasattr(reconnect_from, 'prev_terraria_protocol'):
            work.terraria_protocol.world_name = getattr(
                reconnect_from.prev_terraria_protocol, 'world_name', None)
    work.terraria = server
    return work

#-------------------------------------------------------------------------------
def kill_work(work, remove=True):
    if remove and hasattr(work, 'terraria'):
        del work.terraria
    terraria_protocol.close(work)
    try: work.destroy()
    except socket.error: pass
    try: work.shutdown(socket.SHUT_RDWR)
    except socket.error: pass
    try: work.close()
    except socket.error: pass

#==============================================================================#
@ab_link('BRIDGE')
def ab_bridge(ab_mode, target, msg, source, **kwds):
    work = te_work.get(target.lower())
    if work is None or not hasattr(work, 'terraria_protocol'): return
    msg = strip_codes(msg)
    if MAX_CHAT_LENGTH is not None:
        max_len = MAX_CHAT_LENGTH - len('<%s> ' % work.terraria.user)
        while len(msg) > max_len:
            head, msg = msg[:max_len-3]+'...', '...'+msg[max_len-3:]
            terraria_protocol.chat(work, head)
    terraria_protocol.chat(work, msg)

@ab_link(('BRIDGE', 'NAMES_REQ'))
def h_bridge_names_req(bot, target, source, query):
    work = te_work.get(target.lower())
    if work is None: return

    name = world_name(work)
    if query and name.lower() not in (query.lower(), '+'+query.lower()): return

    if not hasattr(work, 'terraria_protocol') or work.terraria_protocol.stage < 3:
        bridge.notice(bot, target, 'NAMES_ERR', source, name,
            'No contact with server.')
        return

    names = work.terraria_protocol.players.values()
    if target != source:
        names = [bridge.substitute_name(target, n) for n in names]
    bridge.notice(bot, target, 'NAMES_RES', source, name, names)

#==============================================================================#
@te_link('CHAT')
def te_chat(work, slot, colour, text):
    no_echo = [False]
    echo_lines = []
    event_type = None
    agent = work.terraria.user

    if slot == 255:
        match = re.match(r'((?P<sn>\[\S+\])|\*(?P<an>\S+))\s*(?P<m>.*)', text)
        if match:
            event_type = 'MESSAGE' if match.group('sn') else 'ACTION'
            event_name = match.group('sn') or match.group('an')
            event_text = match.group('m')
    else:
        event_type = 'MESSAGE'
        event_name = work.terraria_protocol.players.get(slot, slot)
        event_text = text

    if event_type is not None:
        reply = bridge.substitute_reply(
            context       = work.terraria.name,
            local_name    = event_name,
            msg_local     = lambda m: terraria_protocol.chat(work, strip_codes(m)),
            msg_bridge    = lambda m: echo_lines.append(('<%s> %s' % (agent, m),
                                                         {'no_proxy': True})),
            cancel_bridge = lambda: operator.setitem(no_echo, 0, True))
        yield util.msign(ab_mode, ('BRIDGE', event_type), ab_mode,
            event_name, work.terraria.name, event_text, reply)

    if not no_echo[0] and slot != work.terraria_protocol.slot \
    and not (slot == 255 and message_ignored(text) \
    and len(work.terraria_protocol.players) == 1):
        if slot == 255:
            text = sub_text(work, text)
        else:
            name = work.terraria_protocol.players.get(slot, slot)
            text = '<%s> %s' % (sub_name(work, name), text)
        yield sign('TERRARIA', work, text)

    for line, kwds in echo_lines:
        yield sign('TERRARIA', work, sub_text(line), **kwds)

def sub_text(work, text):
    return bridge.substitute_text(work.terraria.name, text)

def sub_name(work, name):
    return bridge.substitute_name(work.terraria.name, name)

def strip_codes(msg):
    return re.sub(r'[\x00-\x1f]', '', msg)

#-------------------------------------------------------------------------------
@te_link('DISCONNECT')
def te_disconnect(work, msg):
    if not msg.endswith('You are not using the same version as this server.'):
        return

    state = get_state()
    state = state.get(repr(work.terraria.address), dict())
    base_version = state.get('version', terraria_protocol.DEFAULT_VERSION)
    base_version = int(re.search(r'\d+', base_version).group())

    version = work.terraria_protocol.version_number
    version = 2*base_version - version + (1 if version <= base_version else 0)
    if version > 0:
        yield reconnect_work(
            work,
            version = 'Terraria%s' % version,
            delay   = VERSION_RECONNECT_DELAY_SECONDS)
    else:
        yield sign('TERRARIA', work, 'Error: incompatible server version.')
        disconnect_work(work)
    raise Stop

#-------------------------------------------------------------------------------
@te_link('CONNECTION_APPROVED')
def te_connection_approved(work, *args):
    state = get_state()
    server_state = state.get(repr(work.terraria.address), dict())
    server_state['version'] = work.terraria_protocol.version
    state[repr(work.terraria.address)] = server_state
    put_state(state)

#-------------------------------------------------------------------------------
@te_link(untwisted.event.CLOSE)
def te_close(work):
    if not hasattr(work, 'terraria_protocol'): return
    if work.terraria_protocol.stage < 3: return
    yield sign('TERRARIA', work, 'Disconnected from server.')

#-------------------------------------------------------------------------------
@te_link('DISCONNECT')
@te_link(untwisted.event.RECV_ERR)
def te_disconnect_recv_err(work, info):
    if work.terraria_protocol.stage < 3: return
    yield sign('TERRARIA', work, 'Disconnected from server: %s' % info)

#-------------------------------------------------------------------------------
@te_link('DISCONNECT')
@te_link(untwisted.event.RECV_ERR)
@te_link(untwisted.event.CLOSE)
def te_disconnect_recv_err_close(work, *args):
    yield reconnect_work(work)

#-------------------------------------------------------------------------------
@te_link('TERRARIA')
def te_terraria(work, msg, **kwds):
    wname = world_name(work)
    yield util.msign(ab_mode, 'TERRARIA', ab_mode,
        work.terraria.name, msg, wname, **kwds)

#==============================================================================#
def reconnect_work(work, version=None, delay=None):
    return util.msign(ab_mode, 'terraria.reconnect_work', work, version, delay)

@ab_link('terraria.reconnect_work')
def h_reconnect_work(work, version, delay):
    server = work.terraria
    disconnect_work(work, remove=False)
    yield runtime.sleep(delay or RECONNECT_DELAY_SECONDS)
    new_work = init_work(server, version=version, reconnect_from=work)
    te_work[server.name.lower()] = new_work

def disconnect_work(work, remove=True):
    server = work.terraria
    kill_work(work, remove=remove)
    if remove:
        del te_work[server.name.lower()]

def world_name(work):
    wname = None
    if hasattr(getattr(work, 'terraria_protocol', None), 'world_name'):
        wname = work.terraria_protocol.world_name
    if wname is None and hasattr(
    getattr(work, 'prev_terraria_protocol', None), 'world_name'):
        wname = work.prev_terraria_protocol.world_name
    if wname is None and hasattr(work.terraria, 'display'):
        wname = work.terraria.display
    if wname is None:
        wname = work.terraria.name
    return '+' + wname

def message_ignored(msg):
    for imsg in IGNORE_MESSAGES:
        if isinstance(imsg, str):
            if msg == imsg: return True
        elif hasattr(imsg, 'match'):
            if imsg.match(msg): return True
    return False

