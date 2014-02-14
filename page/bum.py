import random
import re

from message import reply
import util

MINLEN  = 5
MAXLEN  = 100
IFREQ   = 800

link, install, uninstall = util.LinkSet().triple()

@link('MESSAGE_IGNORED')
def h_message_ignored(bot, id, target, msg):
    if not target: return
    if random.randrange(IFREQ) != 0: return
    if len(msg) > MAXLEN or len(msg) < MINLEN: return

    msg = re.split(r'(\W+)', msg, re.U | re.L)
    index = random.randrange(len(msg)) & ~1
    word = msg[index]
    if word == '': return

    msg[index] = \
        'BUM' if word.isupper() else \
        'Bum' if word[0].isupper() else \
        'bum'
    msg = ''.join(msg)
    reply(bot, id, target, msg, prefix=False)
