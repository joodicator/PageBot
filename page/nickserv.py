import traceback
import time
import re

from untwisted.magic import sign, hold
import runtime
import util

link, ls_install, ls_uninstall = util.LinkSet().triple()
REGISTERED = 'PRE_AUTOJOIN'
IDENTIFIED = ('AFTER', REGISTERED, __name__)

installed = False

def install(bot):
    global installed
    if installed: raise util.AlreadyInstalled
    installed = True
    util.event_sub(bot, REGISTERED, IDENTIFIED)
    ls_install(bot)
    
def uninstall(bot):
    global installed
    if not installed: raise util.NotInstalled
    installed = False
    ls_uninstall(bot)
    util.event_sub(bot, IDENTIFIED, REGISTERED)

conf_cache = None
def conf(*args, **kwds):
    global conf_cache
    if conf_cache is None:
        try:
            conf_cache = util.fdict('conf/nickserv.py', util.__dict__)
        except IOError:
            traceback.print_exc()
            conf_cache = None
    return conf_cache and conf_cache.get(*args, **kwds)

@link(REGISTERED)
def registered(bot, *rargs):
    if conf('password') and bot.nick == getattr(bot, 'auto_nick', None):
        nick_status = yield status(bot, bot.conf['nick'])
        if nick_status == 1:
            bot.send_msg(
                conf('nickserv').nick,
                'GHOST %s %s' % (bot.conf['nick'], conf('password')))
            bot.send_cmd('NICK %s' % bot.conf['nick'])
    if conf('password'):
        timeout = yield runtime.timeout(30)
        yield hold(bot, 'NICKSERV_REGISTERED', timeout)
    yield sign(IDENTIFIED, bot, *rargs)

@link('MODE')
def h_mode(bot, source, target, modes, *args):
    if target.lower() != bot.nick.lower(): return
    if not re.search(r'\+[a-zA-Z]*r', modes): return
    yield sign('NICKSERV_REGISTERED', bot)

@link('UNOTICE')
def notice(bot, id, target, msg):
    if target is not None: return
    if not conf('nickserv'): return
    nickserv = conf('nickserv')
    if id.nick.lower() != nickserv.nick.lower(): return
    if (id.user, id.host) != (nickserv.user, nickserv.host):
        raise Exception('%s is %s@%s; %s@%s expected.'
            % (id.nick, id.user, id.host, nickserv.user, nickserv.host))
    yield sign('NICKSERV_NOTICE', bot, id, msg)

@link('NICKSERV_NOTICE')
def nickserv_notice(bot, id, msg):
    if conf('prompt') and conf('password') and msg.startswith(conf('prompt')):
        bot.send_msg(id.nick, 'IDENTIFY %s' % conf('password'))
        return
    final = conf('final')
    if final and msg.startswith(final):
        yield sign('NICKSERV_REGISTERED', bot)
        return

#-------------------------------------------------------------------------------
# yield status(bot, nick) - the NickServ STATUS of nick, or None.
@util.mfun(link, 'nickserv.status')
def status(bot, nick, ret):
    sdict = yield statuses(bot, [nick])
    yield ret(sdict.get(nick.lower()))

#-------------------------------------------------------------------------------
# sdict = yield statuses(bot, nicks) - sdict[nick.lower()] is STATUS of nick.
STATUS_BATCH = 1
STATUS_CACHE_SECONDS = 3
status_cache = dict()
@util.mfun(link, 'nickserv.statuses')
def statuses(bot, nicks, ret):
    global status_cache
    earliest = time.time() - STATUS_CACHE_SECONDS
    for nick, (status, stime) in status_cache.items():
        if stime < earliest:
            del status_cache[nick]

    nicks = map(str.lower, nicks)
    send_nicks = [n for n in nicks if n not in status_cache]
    for i in xrange(0, len(send_nicks), STATUS_BATCH):
        batch_nicks = ' '.join(send_nicks[i:i+STATUS_BATCH])
        bot.send_msg(conf('nickserv').nick, 'STATUS %s' % batch_nicks)

    result, remain = dict(), set()
    for nick in nicks:
        if nick not in status_cache:
            status_cache[nick] = (None, time.time())
            remain.add(nick)
        elif status_cache[nick][0] == None:
            remain.add(nick)
        else:
            result[nick] = status_cache[nick][0]

    if remain:
        timeout = yield runtime.timeout(10 + len(nicks)/10)
    while remain:
        event, args = yield hold(bot, 'NICKSERV_NOTICE', timeout)
        if event == timeout: break
        e_bot, e_id, e_msg = args
        match = re.match(r'STATUS\s+(?P<nick>\S+)\s+(?P<code>\d+)', e_msg)
        if not match: continue
        nick, code = match.groups()
        if nick.lower() not in remain: continue

        result[nick.lower()] = int(code)
        remain.remove(nick.lower())
        status_cache[nick.lower()] = (int(code), time.time())

    yield ret(result)
