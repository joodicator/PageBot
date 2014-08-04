import channel
import control
import util

link, link_install, uninstall = util.LinkSet().triple()

credentials = {
    name.lower(): creds
    for (name, creds) in util.fdict('conf/identity.py').iteritems() }

has_host = dict()
has_access = dict()

#===============================================================================
def install(bot):
    for dependency in 'channel', 'nickserv',:
        try:
            __import__(dependency).install(bot)
        except control.AlreadyInstalled:
            pass 
    link_install(bot)

def add_credentials(priv, *creds):
    old_creds = credentials.get(name.lower(), [])
    credentials[name.lower()] = old_creds + creds

#===============================================================================
# yield check_access(bot, nick, name) --> True iff nick has access to name.
@util.mfunc(link, 'identity.check_access')
def check_access(bot, nick, name, ret):
    nick, name = nick.lower(), name.lower()
    if name in has_access.get(nick, set()):
        yield ret(True); return

    for cred in credentials.get(name, list()):
        if cred[0] == 'hostmask' and len(cred) > 1:
            # Authenticate using a hostmask with wildcards.
            pattern = util.wc_to_re(cred[1])
            host = has_host.get(nick, '')
            if re.match(pattern, host, re.I):
                yield ret(True); return
        elif cred[0] == 'nickserv' and len(cred) > 1:
            # Authenticate using NickServ STATUS.
            cred_nick = cred[1].lower()
            if cred_nick != nick: continue
            status = yield nickserv.status(bot, nick)
            if status > 1:
                yield ret(True); return
        elif cred[0] == 'prev_hosts' and len(cred) > 1:
            # Authenticate using previously authenticated hosts.
            pass
    else:
        yield ret(False)

#===============================================================================
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    host = ('%s!%s@%s' % id).lower()
    has_host[id.nick.lower()] = host

@link('OTHER_PART',     a=lambda id, chan, *args:           (id.nick, chan))
@link('OTHER_KICKED',   a=lambda nick, op_id, chan, *args:  (nick, chan))
def h_other_exit(bot, *args, **kwds):
    exit_nick, exit_chan = map(str.lower, kwds['a'](*args))
    for chan, nicks in channel.track_channels.iteritems():
        if chan == exit_chan:
            continue
        if any(exit_nick == nick.lower() for nick in nicks):
            break
    else:
        has_host.pop(exit_nick, None)
        has_access.pop(exit_nick, None)

@link('OTHER_NICK')
def h_other_nick(bot, id, new_nick):
    old_nick, new_nick = id.nick.lower(), new_nick.lower()

    has_host.pop(old_nick, None)
    new_host = ('%s!%s@%s' % (new_nick, id.user, id.host)).lower()
    has_host[new_nick] = new_host

    if old_nick in has_access:
        has_access[new_nick] = has_access.pop(old_nick)
