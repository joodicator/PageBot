from untwisted.mode import Mode
from untwisted.usual import apply
from untwisted.magic import hold
from util import ID, just, msign
import nickserv
import inspect
import re

passed = set()

# Decorates an untwisted event handler which takes arguments 'bot' and 'id',
# causing its body to be executed iff the specified user is an admin according
# to check(bot, id).
def admin(func):
    def admin_decd(*args, **kwds):
        cargs = inspect.getcallargs(func, *args, **kwds)
        bot, id = cargs['bot'], cargs['id']
        
        with open('conf/admins.txt') as file:
            admins = re.findall(r'\S+', file.read())
        if id.nick not in admins: return

        if id not in passed:
            (_, [_, _, code]) = yield nickserv.status(bot, id.nick)
            if code < 3: return
            passed.add(id)
        
        gen = func(*args, **kwds)
        if not inspect.isgenerator(gen): return
        last = None
        try:
            while True: last = yield gen.send(last)
        except StopIteration: pass
    return admin_decd
