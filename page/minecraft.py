# coding=utf8

from __future__ import print_function

from datetime import datetime
import re
import sys
import socket
import traceback
import operator

from untwisted.mode import Mode
from untwisted.network import Work
from untwisted.event import DATA, BUFFER, FOUND, CLOSE, RECV_ERR
from untwisted.utils import std
from untwisted.utils.common import append, shrug
from untwisted.magic import sign

import util
import debug
import runtime
import bridge
from util import NotInstalled, AlreadyInstalled


RECONNECT_DELAY_SECONDS = 1

conf_servers = util.table('conf/minecraft.py', 'server', socket.__dict__)

mc_work = []
mc_mode = Mode()
mc_mode.domain = 'mc'
mc_link = util.LinkSet()
mc_link.link_module(std)
mc_link.link(DATA, append)
mc_link.link(BUFFER, shrug, '\n')
if '--debug' in sys.argv: mc_link.link_module(debug)

ab_mode = None
ab_link = util.LinkSet()


class MinecraftState(object):
    def __init__(self):
        self.map_name = None
        self.agent = None
    def reload_from(self, prev):
        if hasattr(prev, 'map_name'):
            self.map_name = prev.map_name
        if hasattr(prev, 'agent'):
            self.agent = prev.agent

def init_work(server, reload_from=None, reconnect_from=None):
    sock = socket.socket(server.family, socket.SOCK_STREAM)
    work = Work(mc_mode, sock)
    mc_work.append(work)
    work.minecraft = server
    work.minecraft_state = MinecraftState()
    if hasattr(reconnect_from, 'minecraft_state'):
        work.minecraft_state.reload_from(reconnect_from.minecraft_state)
    elif hasattr(reload_from, 'minecraft_state'):
        work.minecraft_state.reload_from(reload_from.minecraft_state)
    work.setblocking(0)
    work.connect_ex(server.address)
    h_query(work, 'map')
    h_query(work, 'agent')

def kill_work(work, remove=True):
    try: work.destroy()
    except socket.error: pass
    try: work.shutdown(socket.SHUT_RDWR)
    except socket.error: pass
    try: work.close()
    except socket.error: pass
    if remove: mc_work.remove(work)

def reload(prev):
    if not hasattr(prev, 'mc_work'): return
    if not isinstance(prev.mc_work, list): return
    mc_work[:] = prev.mc_work[:]

def install(bot):
    global ab_mode, mc_work
    if ab_mode is not None: raise AlreadyInstalled

    ab_mode = bot
    ab_link.install(ab_mode)

    mc_link.install(mc_mode)
    prev_work, mc_work = mc_work, list()
    for server in conf_servers:
        prev = [w for w in prev_work if w.minecraft.name == server.name]
        if prev:
            init_work(server, reload_from=prev[0])
        else:
            init_work(server)

def reload_uninstall(bot):
    uninstall(bot, reload=True)

def uninstall(bot, reload=False):
    global ab_mode
    if ab_mode is None: raise NotInstalled

    mc_link.uninstall(mc_mode)
    for work in mc_work[:]:
        kill_work(work, remove=not reload)

    ab_link.uninstall(ab_mode)
    ab_mode = None


@ab_link('BRIDGE')
def ab_bridge(bot, target_chan, msg, source, **kwds):
    msg = strip_codes(msg)
    for work in mc_work:
        if work.minecraft.name.lower() != target_chan.lower(): continue
        work.dump(msg + '\n')

@ab_link(('BRIDGE', 'NAMES_REQ'))
def h_bridge_names_req(bot, target, source, name_query):
    for work in mc_work:
        if work.minecraft.name.lower() != target.lower(): continue

        name = work.minecraft_state.map_name or work.minecraft.display or target
        if name_query and name_query.lower() not in (name.lower(), target.lower()):
            continue

        (state, value) = yield query(work, 'players')
        if state == 'success':
            result = value.split()
            if target != source:
                result = [sub_name(work, n) for n in result]
            bridge.notice(
                bot, target, 'NAMES_RES', source, name, result)
        elif state == 'failure':
            bridge.notice(bot, target, 'NAMES_ERR', source, name, value)

@mc_link(FOUND)
def mc_found(work, line):
    line = re.sub(r'§.', '', line)

    match = re.match('!query (\S+) (\S+) (.*)', line)
    if match:
        type, key, body = match.groups()
        head = 'QUERY_' + type.upper()
        for event in head, (head, key):
            yield sign(event, work, type, key, body)
        return

    agent = getattr(work.minecraft_state, 'agent', None)
    if agent:
        for fmt in '<%s>', '* %s ', '%s ':
            if line.startswith(fmt % agent): return

    no_echo = [False]
    echo_lines = []
    match = re.match(r'((?P<sn>\[\S+\])|<(?P<mn>\S+)>|\* (?P<an>\S+)) '
        '(?P<msg>.*)', line)
    if match:
        msg = match.group('msg')
        name = match.group('sn') or match.group('mn') or match.group('an')
        event = 'ACTION' if match.group('an') else 'MESSAGE'
        reply = bridge.substitute_reply(
            context       = work.minecraft.name,
            local_name    = name,
            msg_local     = lambda m: work.dump(strip_codes(m) + '\n'),
            msg_bridge    = lambda m: echo_lines.append((
                '<%s> %s' % (sub_name(work, agent), m), {'no_proxy': True})),
            cancel_bridge = lambda: operator.setitem(no_echo, 0, True))
        ab_mode.drive(('BRIDGE', event), ab_mode,
            name, work.minecraft.name, msg, reply)

    if not no_echo[0]:
        if match:
            name_group = next(g for g in ('sn','mn','an') if match.group(g))
            name_s, name_e = match.span(name_group)
            echo(work, line[:name_s] + sub_name(work, name) + line[name_e:])
        else:
            echo(work, sub_text(work, line))

    for line, kwds in echo_lines:
        echo(work, line, **kwds)

def sub_text(work, text):
    return bridge.substitute_text(work.minecraft.name, text)

def sub_name(work, name):
    return bridge.substitute_name(work.minecraft.name, name)

def echo(work, line, **kwds):
    ab_mode.drive('MINECRAFT', ab_mode,
        work.minecraft.name, line,
        work.minecraft_state.map_name or work.minecraft.display,
        **kwds)

def strip_codes(msg):
    return re.sub(r'[\x00-\x1f]', '', msg).replace('§', 'S')

@mc_link(CLOSE)
@mc_link(RECV_ERR)
def mc_close_recv_error(work, *args):
    kill_work(work)
    yield runtime.sleep(RECONNECT_DELAY_SECONDS)
    init_work(work.minecraft, reconnect_from=work)

@mc_link(('QUERY_SUCCESS', 'map'))
def h_query_success_map(work, type, key, val):
    work.minecraft_state.map_name = val

@mc_link(('QUERY_SUCCESS', 'agent'))
def h_query_success_map(work, type, key, val):
    work.minecraft_state.agent = val


# (status, value) = yield minecraft.query(key),
# where status is 'result' or 'failure'
def query(work, key):
    return util.mmcall(ab_mode, 'minecraft.query', work, key)


@ab_link('minecraft.query')
def h_query(work, key):
    work.dump('?query %s\n' % key)

@mc_link(('QUERY_SUCCESS'))
@mc_link(('QUERY_FAILURE'))
def h_query_success_failure(work, type, key, val):
    yield util.msign(ab_mode, ('minecraft.query', work, key), (type, val))
