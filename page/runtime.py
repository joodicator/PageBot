import time
import sys

from untwisted.mode import Mode
from untwisted.event import TICK, CLOSE
from untwisted.magic import sign
from untwisted.core import gear

import util
import debug


EXIT_DELAY_SECONDS = 0.1

b_link = util.LinkSet()

mode = Mode()
mode.domain = 'run'
mode.poll = mode
gear.tick_list.append(mode)
m_link = util.LinkSet()
#if '--debug' in sys.argv: m_link.link_module(debug)

sleepers = list()


def install(bot):
    b_link.install(bot)
    m_link.install(mode)

def uninstall(bot):
    m_link.uninstall(mode)
    b_link.uninstall(bot)

def reinstall(prev):
    global mode
    if hasattr(prev, 'mode') and prev.mode:
        mode = prev.mode


# Schedule an action, which may be yielded in an untwisted event handler,
# to be yielded after all handlers for the current event have run.
@util.msub(b_link, 'runtime.later')
def later(action):
    yield sleep(0)
    yield action


@util.mfun(b_link, 'runtime.timeout')
def timeout(delta, ret):
    token = ('TIMEOUT',object())
    yield ret(token)    
    yield sleep(delta)
    yield sign(token)


def sleep(delta):
    return util.mmcall(mode, 'runtime.sleep', time.time() + delta)

@m_link('runtime.sleep')
def h_sleep(until):
    sleepers.append(until)
    sleepers.sort()

@m_link(TICK)
def h_tick(mode):
    while len(sleepers):
        if sleepers[0] > time.time(): break
        yield sign(('runtime.sleep', sleepers.pop(0)), None)

@b_link(CLOSE)
def h_close(bot):
    if bot.closing: return
    bot.closing = True
    print '! disconnected'
    yield sign('CLOSING', bot)
    yield sleep(EXIT_DELAY_SECONDS)
    bot.destroy()
    sys.exit(0)

@b_link('EXCEPTION')
def h_exception(bot, e):
    if bot.closing: return
    bot.closing = True
    print '! uncaught exception'
    yield sign('CLOSING', bot)
    yield sleep(EXIT_DELAY_SECONDS)
    bot.destroy()
    raise e

@b_link('AUTONICK')
def h_nick(bot):
    yield sleep(15)
    while True:
        if bot.nick != bot.auto_nick: break
        bot.send_cmd('NICK %s' % bot.conf['nick'])
        yield sleep(30)

@b_link('OTHER_NICK')
@b_link('OTHER_QUIT')
def h_other_nick(bot, id, *args):
    if (hasattr(bot, 'auto_nick') and bot.nick == bot.auto_nick
    and id.nick.lower() == bot.conf['nick'].lower()):
        bot.send_cmd('NICK %s' % bot.conf['nick'])
