import re

from untwisted.magic import sign, hold
import runtime
import util

link, ls_install, ls_uninstall = util.LinkSet().triple()
REGISTERED = '001'
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

def conf(*args, **kwds):
    return util.fdict('conf/nickserv.py', util.__dict__).get(*args, **kwds)

@link(REGISTERED)
def registered(bot, *rargs):
    if conf('password'):
        yield hold(bot, 'NICKSERV_REGISTERED')
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
@util.mfun(link, 'nickserv.statuses')
def statuses(bot, nicks, ret):
    for i in xrange(0, len(nicks), 16):
        batch_nicks = ' '.join(nicks[i:i+16])
        bot.send_msg(conf('nickserv').nick, 'STATUS %s' % batch_nicks)

    timeout = yield runtime.timeout(5 + len(nicks)/10)
    result, remain = dict(), set(n.lower() for n in nicks)
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
    yield ret(result)
