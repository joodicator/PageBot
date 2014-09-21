import random
import math
import re
import time

from message import reply
import util

link, install, uninstall = util.LinkSet().triple()

PERIOD = 60
last = dict()

def laugh():
    def length():
        return max(1, int(math.ceil(random.normalvariate(2.5, 1))))
    def huea(m):
        return "H" + "".join((random.choice("EAU") for n in xrange(m)))
    def heahuea(m):
        return "".join(huea(length()) for n in xrange(m))
    return heahuea(length())

@link('MESSAGE')
def h_message(bot, id, target, msg):
    now = time.time()
    if target and target in last and now < last[target] + PERIOD:
        return
    if re.search("(h[eau]+){2,}", msg, re.I):
        last[target] = now        
        reply(bot, id, target, laugh(), prefix=False)
