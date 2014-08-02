from untwisted.magic import sign, hold
import util
import re

link, ls_install, ls_uninstall = util.LinkSet().triple()
REGISTERED = '001'
IDENTIFIED = ('AFTER', REGISTERED, __name__)

def install(bot):
    util.event_sub(bot, REGISTERED, IDENTIFIED)
    ls_install(bot)
    
def uninstall(bot):
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
    match = re.match(r'STATUS\s+(?P<nick>\S+)\s+(?P<code>\d+)', msg)
    if match:
        nick, code = match.groups()
        yield sign(('NICKSERV_STATUS', nick), bot, id, int(code))


# Returns an object that may be yielded in an untwisted event handler to obtain
# the integer returned by NickServ's STATUS command for the given nick.
def status(bot, nick):
    return util.mcall('nickserv.status', bot, nick)

@link('nickserv.status')
def h_nickserv_status(bot, nick):
    ret = lambda a: sign(('nickserv.status', bot, nick), a)
    bot.send_msg(conf('nickserv').nick, 'STATUS %s' % nick)
    (_, [_, _, code]) = yield hold(bot, ('NICKSERV_STATUS', nick))
    yield ret(code)
