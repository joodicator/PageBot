import re
import util
import time
import identity
import inspect
import os.path

from untwisted.mode import Mode
from untwisted.usual import apply
from untwisted.magic import hold, sign

from util import ID, just, msign, LinkSet
from message import reply

link, install, uninstall = LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'identity')

ADMINS_FILE = 'conf/admins.txt'
PASSWORD_FILE = 'conf/auth_password.txt'
IDENTIFY_DURATION_S = 60*60

passed = set()
identified = dict()

def reload(prev):
    if hasattr(prev, 'passed') and isinstance(prev.passed, set):
        passed.update(prev.passed)
    if hasattr(prev, 'identified') and isinstance(prev.identified, dict):
        identified.update(prev.identified)

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
        elif 'target' in cargs or 'chan' in cargs:
            target = cargs.get('target') or cargs.get('chan')
            reply(bot, id, cargs['target'], 'Access denied.')
    return admin_decd


# Returns an object that may be yielded in an untwisted event handler to obtain
# True if the given user is authenticated as an admin, or otherwise False.
@util.mfun(link, 'auth.check')
def check(bot, id, ret):
    if identify_check(id):
        yield ret(True); return

    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE) as file:
            admins = re.findall(r'\S+', file.read())

        for admin in admins:
            if any(c in admin for c in '!@*?'):
                # Verify against a hostmask with wildcards.
                hostmask = '%s!%s@%s' % id
                if re.match(util.wc_to_re(admin), hostmask, re.I):
                    yield ret(True); return
            else:
                # Verify an access name according to the 'identity' module.
                access = yield identity.check_access(bot, id, admin)
                if access:
                    yield ret(True); return
    
    yield ret(False)

#===============================================================================
@link('!id')
@link('!identify')
def h_identify(bot, id, target, args, full_msg):
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE) as file:
            password = file.read().strip()
        if args.strip() == password:
            identified[id] = time.clock()
            reply(bot, id, target, 'Authentication successful.')
        else:
            reply(bot, id, target, 'Authentication failed: incorrect password.')
    else:   
        reply(bot, id, target, 'No admin password is configured.')

def identify_check(id):
    if id not in identified:
        return False
    elif time.clock() - identified[id] > IDENTIFY_DURATION_S:
        del identified[id]
        return False
    else:
        identified[id] = time.clock()
        return True
