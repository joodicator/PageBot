# coding=utf8

from __future__ import print_function

import re
import sys
import socket

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

def init_work(server):
    sock = socket.socket(server.family, socket.SOCK_STREAM)
    work = Work(mc_mode, sock)
    mc_work.append(work)
    work.minecraft = server
    work.minecraft_state = MinecraftState()
    work.setblocking(0)
    work.connect_ex(server.address)
    h_query(work, 'map')

def kill_work(work):
    work.destroy()
    work.shutdown(socket.SHUT_RDWR)
    work.close()
    mc_work.remove(work)

def install(bot):
    global ab_mode
    if ab_mode is not None: raise AlreadyInstalled

    ab_mode = bot
    ab_link.install(ab_mode)

    mc_link.install(mc_mode)
    for server in conf_servers:
        init_work(server)

def uninstall(bot):
    global ab_mode
    if ab_mode is None: raise NotInstalled

    mc_link.uninstall(mc_mode)
    while len(mc_work):
        kill_work(mc_work[0])

    ab_link.uninstall(ab_mode)
    ab_mode = None


@ab_link('BRIDGE')
def ab_bridge(bot, target_chan, msg):
    msg = re.sub(r'[\x00-\x1f]', '', msg).replace('§', 'S')
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
            bridge.notice(bot, target, 'NAMES_RES', source, name, value.split())
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

    for fmt in '<%s>', '* %s', '%s':
        if line.startswith(fmt % work.minecraft.agent): return

    match = re.match(r'(<\S+>|\[\S+\]) !online(?P<args> .*|$)', line)
    if match:
        args = match.group('args').strip()
        bridge.notice(ab_mode, work.minecraft.name, 'NAMES_REQ',
                      work.minecraft.name, args)

    if re.match(r'(<\S+> |\[\S+\] |\* \S+ |)!', line): return

    yield util.msign(ab_mode, 'MINECRAFT', ab_mode,
        work.minecraft.name, line,
        work.minecraft_state.map_name or work.minecraft.display)

@mc_link(CLOSE)
@mc_link(RECV_ERR)
def mc_close_recv_error(work, *args):
    kill_work(work)
    yield runtime.sleep(RECONNECT_DELAY_SECONDS)
    init_work(work.minecraft)

@mc_link(('QUERY_SUCCESS', 'map'))
def h_query_success_map(work, type, key, val):
    work.minecraft_state.map_name = val


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
