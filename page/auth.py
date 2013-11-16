import re
import util
import time
import nickserv
import inspect

from untwisted.mode import Mode
from untwisted.usual import apply
from untwisted.magic import hold, sign

from util import ID, just, msign, LinkSet
from message import reply

link, install, uninstall = LinkSet().triple()

IDENTIFY_DURATION_S = 60*60

passed = set()
identified = dict()

# Decorates an untwisted event handler which takes arguments 'bot' and 'id',
# causing its body to be executed iff the specified user is an admin according
# to check(bot, id).
def admin(func):
    def admin_decd(*args, **kwds):
        cargs = inspect.getcallargs(func, *args, **kwds)
        bot, id = cargs['bot'], cargs['id']
        is_admin = yield check(bot, id)
        if is_admin:
            token = object()
            bot.link(token, func)
            bot.drive(token, *args, **kwds)
            bot.unlink(token, func)
    return admin_decd


# Returns an object that may be yielded in an untwisted event handler to obtain
# True if the given user is authenticated as an admin, or otherwise False.
def check(bot, id):
    return util.mcall('auth.check', bot, id)

@link('auth.check')
def h_auth_check(bot, id):
    ret = lambda a: sign(('auth.check', bot, id), a)

    if identify_check(id):
        yield ret(True)

    with open('conf/admins.txt') as file:
        admins = re.findall(r'\S+', file.read())

    if '*!%s@%s' % (id.user, id.host) in admins:
        yield ret(True)
    elif '*!*@%s' % id.host in admins:
        yield ret(True)
    elif id.nick not in admins:
        yield ret(False)
    elif id in passed:
        yield ret(True)
    else:
        code = yield nickserv.status(bot, id.nick)
        if code >= 3:
            passed.add(id)
            yield ret(True)
        else:
            yield ret(False)

#===============================================================================

@link('!id')
@link('!identify')
def h_identify(bot, id, target, args, full_msg):
    with open('conf/auth_password.txt') as file:
        password = file.read().strip()
    if args.strip() == password:
        identified[id] = time.clock()
        reply(bot, id, target, 'Authentication successful.')
    else:
        reply(bot, id, target, 'Authentication failed: incorrect password.')

def identify_check(id):
    if id not in identified:
        return False
    elif time.clock() - identified[id] > IDENTIFY_DURATION_S:
        del identified[id]
        return False
    else:
        identified[id] = time.clock()
        return True
