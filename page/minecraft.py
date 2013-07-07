# coding=utf8

from __future__ import print_function

import socket

from untwisted.mode import Mode
from untwisted.network import Work
from untwisted.event import DATA, BUFFER, FOUND, CLOSE, RECV_ERR
from untwisted.utils import std
from untwisted.utils.common import append, shrug

import re
import sys
import util
import debug
import runtime
from control import NotInstalled, AlreadyInstalled


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


def init_work(server):
    sock = socket.socket(server.family, socket.SOCK_STREAM)
    work = Work(mc_mode, sock)
    mc_work.append(work)
    work.minecraft = server
    work.setblocking(0)
    work.connect_ex(server.address)

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


@mc_link(FOUND)
def mc_found(work, line):
    line = re.sub(r'§.', '', line)
    if line.startswith('<%s>' % work.minecraft.agent): return
    if re.match(r'(<\S+> |\* \S+ |)!', line): return
    yield util.msign(ab_mode, 'MINECRAFT', ab_mode, work.minecraft.name, line)


@mc_link(CLOSE)
@mc_link(RECV_ERR)
def mc_close_recv_error(work, *args):
    kill_work(work)
    yield runtime.sleep(RECONNECT_DELAY_SECONDS)
    init_work(work.minecraft)
