from untwisted.mode import Mode
from untwisted.usual import apply
from untwisted.magic import hold, sign
from util import ID, just, msign, LinkSet
import util
import nickserv
import inspect
import re

link, install, uninstall = LinkSet().triple()

passed = set()

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

    with open('conf/admins.txt') as file:
        admins = re.findall(r'\S+', file.read())

    if id.nick not in admins:
        yield ret(False)
    elif id in passed:
        yield ret(True)
    else:
        code = yield nickserv.status(bot, id.nick)
        if code >= 3:
            yield ret(True)
            passed.add(id)
        else:
            yield ret(False)
