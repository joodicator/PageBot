from collections import defaultdict
from collections import namedtuple
import time
import array
import re

import util
link, install, uninstall = util.LinkSet().triple()

HISTORY_SECONDS = 3600
HISTORY_ENTRIES = 250
SCORE_MUL_HOUR  = 0.1
SCORE_MUL_10MSG = 0.2
SCORE_POLE_SEC  = 1.5
SCORE_POLE_MAX  = 2
SCORE_MUL_OTHER = 0.5
SCORE_MIN_SELF  = 0.1
SCORE_THRESHOLD = 5

Msg = namedtuple('Msg', ('time', 'id', 'text'))

# chan_history[chan.lower()] = [Msg(...), Msg(...), ...]
chan_history = defaultdict(list)

@link('PRIVMSG')
@link('UNOTICE')
def h_message(bot, id, chan, text):
    if not chan.startswith('#'): return
    flooding = handle_message()

    msg = Msg(time=time.time(), id=id, text=text)
    score = handle_message(msg, id, chan)
    if score > SCORE_THRESHOLD:
        punish(bot, id, chan)

def punish(bot, id, chan):
    pass

def handle_msg(msg, id, chan):
    chan = chan.lower()
    history = chan_history[chan]
    del history[:len(history)-HISTORY_ENTRIES]
    while history and msg.time - history[0].time > HISTORY_SECONDS:
        del history[0]
    score = score_msg(msg, history)
    history.append(msg)
    chan_history[chan] = history   
    return score

def score_msg(msg, history):
    score = 0
    for i in xrange(1, len(history)+1):
        hmsg = history[-i]
        tdif = msg.time - hmsg.time
        part = similarity(msg.text, hmsg.text)**2
        if same_user(msg.id, hmsg.id):
            part = max(SCORE_MIN_SELF, part)
        else:
            part *= SCORE_MUL_OTHER
        part *= SCORE_MUL_HOUR**(tdif/3600.0)
        tmin = SCORE_POLE_SEC/(SCORE_POLE_MAX - 1)
        part *= (1 + SCORE_POLE_SEC/max(tmin, tdif))
        part *= SCORE_MUL_10MSG**(i/10.0)
        score += part

    return score

def same_user(id1, id2):
    return id1.host == id2.host and \
           (id1.user == id2.user or id1.user[:1] == id2.user[:1] == '~')

WORD_RE = re.compile(r'(\w+)', re.U)
def similarity(str1, str2):
    str1, str2 = WORD_RE.split(str1), WORD_RE.split(str2)
    lcs = longest_common_substring(str1, str2)
    return float(len(lcs)) / float(max(len(str1), len(str2)))

def longest_common_substring(str1, str2):
    len1, len2 = len(str1), len(str2)
    if len1 > len2:
        str1, str2, len1, len2 = str2, str1, len2, len1
    bend, blen = 0, 0
    for d in xrange(len2-1):
        cend, clen = 0, 0
        for i in xrange(min(len1, len2-d)):
            if str1[i] == str2[i+d]:
                cend, clen = i+1, clen+1
                if clen > blen:
                    bend, blen = cend, clen
            else:
                clen = 0
    return str1[bend-blen:bend]
