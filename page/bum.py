import random
import re

from message import reply
from channel import not_quiet
import util

MINLEN  = 5
MAXLEN  = 100
IFREQ   = 1000

ignore_words = set()
ignore_prefixes = set()
ignore_suffixes = set()
with open('static/bum_ignore.txt') as file:
    for line in file:
        line = line.strip().lower()
        if not line: continue
        if line.startswith("'"): ignore_suffixes.add(line)
        elif line.endswith("'"): ignore_prefixes.add(line)
        else:                    ignore_words.add(line)

link, install, uninstall = util.LinkSet().triple()

@link('MESSAGE_IGNORED')
@not_quiet()
def h_message_ignored(bot, id, target, msg):
    if not target: return
    if random.randrange(IFREQ) != 0: return
    if len(msg) > MAXLEN or len(msg) < MINLEN: return
    msg = bum_replace(msg)
    if not msg: return
    reply(bot, id, target, msg, prefix=False)

def bum_replace(str_msg):
    msg = bum_split(str_msg)
    indices = range(0, len(msg), 2)

    if str_msg.startswith('\1'):
        if msg.startswith('\1ACTION '):
            del indices[0]
        else:
            return

    indices = filter(lambda i:  
        msg[i] and not is_ignored(msg[i]), indices)
    if not indices:
        return
    index = random.choice(indices)

    msg[index] = \
        'BUM' if msg[index].isupper() else \
        'Bum' if msg[index][0].isupper() else \
        'bum'
    return ''.join(msg)

def bum_split(msg):
    return re.split(r"([^\w'-]+)", msg, re.U | re.L)

def is_ignored(word):
    word = word.lower()
    if word == 'bum': return True
    if word in ignore_words: return True
    bits = word.split("'")
    if len(bits) < 2: return False
    if bits[0]+"'" in ignore_prefixes: return True
    if "'"+bits[-1] in ignore_suffixes: return True
    return False
