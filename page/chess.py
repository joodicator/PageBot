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
from util import NotInstalled, AlreadyInstalled

SOCKET_ADDRESS = 'state/chess'
RECONNECT_DELAY_SECONDS = 1

ch_work = []
ch_mode = Mode()
ch_mode.domain = 'ch'
ch_link = util.LinkSet()
ch_link.link_module(std)
ch_link.link(DATA, append)
ch_link.link(BUFFER, shrug, '\n')
if '--debug' in sys.argv: ch_link.link_module(debug)

ab_mode = None
ab_link = util.LinkSet()


@ab_link(('HELP', 'chess'))
def h_help(bot, reply, args):
    reply('chess start',
        'Starts a new game of chess.')
    reply('chess rf RF',
        'Moves the piece at rank r file f to rank R file F.')
    reply('chess M [r|f|rf] RF',
        'Moves a piece of type M to rank R file F'
        ' (moving from rank r and/or file f, if specified).')
    reply('chess [r|f] RF',
        'Moves a pawn to rank R file F'
        ' (moving from rank r or file f, if specified).')
    reply('chess stop',
        'Cancels the current game of chess.')

def init_work(address):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    work = Work(ch_mode, sock)
    work.address = address
    ch_work.append(work)
    work.setblocking(0)
    work.connect_ex(address)

def kill_work(work):
    work.destroy()
    work.shutdown(socket.SHUT_RDWR)
    work.close()
    ch_work.remove(work)

def install(bot):
    global ab_mode
    if ab_mode is not None: raise AlreadyInstalled

    ab_mode = bot
    ab_link.install(ab_mode)

    ch_link.install(ch_mode)
    init_work(SOCKET_ADDRESS)

def uninstall(bot):
    global ab_mode
    if ab_mode is None: raise NotInstalled

    ch_link.uninstall(ch_mode)
    while len(ch_work):
        kill_work(ch_work[0])

    ab_link.uninstall(ab_mode)
    ab_mode = None

@ab_link('!chess')
def h_chess(bot, id, target, args, full_msg):
    if not target: return
    for work in ch_work:
        work.dump('%s <%s> %s\n' % (target, id.nick, args))

@ch_link(FOUND)
def ch_found(work, line):
    match = re.match(r'(#\S+) (.*)', line.strip())
    if not match: return
    ab_mode.send_msg(match.group(1), match.group(2))

@ch_link(CLOSE)
@ch_link(RECV_ERR)
def ch_close_recv_error(work, *args):
    kill_work(work)
    yield runtime.sleep(RECONNECT_DELAY_SECONDS)
    init_work(work.address)
