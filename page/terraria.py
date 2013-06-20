#==============================================================================#
import util
import control
import runtime
import terraria_protocol

from untwisted.magic import sign
import untwisted.event
import untwisted.mode
import untwisted.network

import traceback
import socket

#==============================================================================#
RECONNECT_DELAY_SECONDS = 10
MAX_CHAT_LENGTH = 80

servers = util.table('conf/terraria.py', 'server')

te_mode = untwisted.mode.Mode()
te_link = util.LinkSet()
te_link.link_module(terraria_protocol)
te_work = dict()

ab_mode = None
ab_link = util.LinkSet()

#==============================================================================#
def install(bot):
    global ab_mode, te_work
    if ab_mode is not None: raise control.AlreadyInstalled
    ab_mode = bot
    ab_link.install(ab_mode)
    te_link.install(te_mode)

    prev_work, te_work = te_work, dict()
    for work in prev_work.itervalues():
        try: reload_work(work)
        except NameError: trackback.print_exc()

    for server in servers:
        if server.name.lower() not in te_work:
            te_work[server.name.lower()] = init_work(server)

def uninstall(bot):
    global ab_mode
    if ab_mode is None: raise control.NotInstalled
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
        if work.terraria_protocol.stage >= 3:
            msg = 'Disconnected from server: configuration update.'
            te_mode.drive('TERRARIA', work, msg)
        kill_work(work)

def init_work(server, prev=None):
    if prev is None:
        work = untwisted.network.Work(te_mode, socket.socket())
        work.connect_ex(server.address)
        terraria_protocol.login(work, server.user)
    else:
        prev.destroy()
        work = untwisted.network.Work(te_mode, prev.sock)
        work.terraria_protocol = prev.terraria_protocol
        if work.terraria_protocol.stage >= 3:
            te_mode.drive('HEARTBEAT', work)
    work.terraria = server
    return work

def kill_work(work):
    if hasattr(work, 'terraria'): del work.terraria
    terraria_protocol.close(work)
    try: work.destroy()
    except: traceback.print_exc()
    try: work.shutdown(socket.SHUT_RDWR)
    except: traceback.print_exc()
    try: work.close()
    except: traceback.print_exc()

#==============================================================================#
@ab_link('BRIDGE')
def ab_bridge(ab_mode, target, msg):
    work = te_work.get(target.lower())
    if work is None: return
    max_len = MAX_CHAT_LENGTH - len('<%s> ' % work.terraria.user)
    while len(msg) > max_len:
        head, msg = msg[:max_len-3]+'...', '...'+msg[max_len-3:]
        terraria_protocol.chat(work, head)
    terraria_protocol.chat(work, msg)

#==============================================================================#
@te_link('CHAT')
def te_chat(work, slot, colour, text):
    if slot == 255:
        yield sign('TERRARIA', work, text)
    elif slot != work.terraria_protocol.slot:
        name = work.terraria_protocol.players.get(slot, slot)
        yield sign('TERRARIA', work, '<%s> %s' % (name, text))

@te_link(untwisted.event.CLOSE)
def te_close(work):
    if work.terraria_protocol.stage < 3: return
    yield sign('TERRARIA', work, 'Disconnected from server.')

@te_link('DISCONNECT')
@te_link(untwisted.event.RECV_ERR)
def te_disconnect_recv_err(work, info):
    if work.terraria_protocol.stage < 3: return
    yield sign('TERRARIA', work, 'Disconnected from server: %s' % info)

@te_link('DISCONNECT')
@te_link(untwisted.event.RECV_ERR)
@te_link(untwisted.event.CLOSE)
def te_disconnect_recv_err_close(work, *args):
    server = work.terraria
    kill_work(work)
    del te_work[server.name.lower()]
    yield runtime.sleep(RECONNECT_DELAY_SECONDS)
    te_work[server.name.lower()] = init_work(server)

@te_link('TERRARIA')
def te_terraria(work, msg):
    yield util.msign(ab_mode, 'TERRARIA', ab_mode, work.terraria.name, msg)
