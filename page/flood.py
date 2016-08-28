from collections import defaultdict
from collections import namedtuple
from itertools import *
import time
import array
import re
import os.path

import util
import channel
link, install, uninstall = util.LinkSet().triple()

CONF_CHANS_FILE = 'conf/flood_chans.py'

HISTORY_SECONDS = 3600
HISTORY_ENTRIES = 250
SCORE_MUL_HOUR = 0.1
SCORE_MUL_10MSG = 0.5
SCORE_MUL_NICKS = 3.0
SCORE_MUL_UPPER = 1.5
SCORE_POLE_SEC = 1.5
SCORE_POLE_MAX = 2.0
SCORE_MUL_OTHER = 0.7
SCORE_MIN_SELF = 0.1
MIN_EFFECTIVE_LEN = 20
MIN_EFFECTIVE_NICKS = 10
SCORE_THRESHOLD = 3.0

Msg = namedtuple('Msg', ('time', 'id', 'text', 'score'))

# chan_history[chan.lower()] = [Msg(...), Msg(...), ...]
chan_history = defaultdict(list)

if os.path.exists(CONF_CHANS_FILE):
    conf_chans = {
        record.channel.lower(): record
        for record in util.table(CONF_CHANS_FILE,
        globals={'DEFAULT':None}) }
else:
    conf_chans = {}

def reload(prev):
    if hasattr(prev, 'chan_history') \
    and isinstance(prev.chan_history, dict):
        for chan, prev_history in prev.chan_history.iteritems():
            if chan not in conf_chans: continue
            history = chan_history[chan]
            history[:] = prev_history
            chan_history[chan] = history

@link('PRIVMSG')
@link('UNOTICE')
def h_message(bot, id, chan, text):
    if chan is None or not chan.startswith('#'): return
    chan = chan.lower()
    if chan not in conf_chans: return

    score = handle_msg(Msg(time.time(), id, text, 0), chan)
    if score > SCORE_THRESHOLD: punish(bot, id, chan)

def punish(bot, id, chan):
    hostmask = '*!%s@%s' % (
        '*' if id.user.startswith('~') else id.user, id.host)
    commands = conf_chans[chan].punish_commands or [
        'MODE %(chan)s +b %(hostmask)s',
        'KICK %(nick)s :%(reason)s']
    for command in commands:
        bot.send_cmd(command % {
            'nick':     id.nick,
            'user':     id.user,
            'host':     id.host,
            'hostmask': hostmask,
            'chan':     chan,
            'reason':   'Flooding detected.'})

def handle_msg(msg, chan):
    chan = chan.lower()
    history = chan_history[chan]
    del history[:len(history)-HISTORY_ENTRIES]
    while history and msg.time - history[0].time > HISTORY_SECONDS:
        del history[0]
    score = score_msg(msg, chan, history)
    history.append(msg._replace(score=score))
    chan_history[chan] = history   
    return score

def score_msg(msg, chan, history):
    score = 0.0
    for i in xrange(1, len(history)+1):
        hmsg = history[-i]
        part = score_msg_part(msg, hmsg, rel_num=i)
        score += part

    nicks = channel.track_channels[chan]
    mnicks = sum(1 for n in nicks if re.search(re.escape(n), msg.text, re.I))
    score *= SCORE_MUL_NICKS**(float(mnicks)/max(MIN_EFFECTIVE_NICKS, len(nicks)))

    uchrs = sum(1 for c in msg.text if c.isupper())
    score *= SCORE_MUL_UPPER**(float(uchrs)/max(MIN_EFFECTIVE_LEN, len(msg.text)))

    return score

def score_msg_part(msg, hmsg, rel_num):
    part = max(1.0, min(2.0, hmsg.score))

    min_eff_len = MIN_EFFECTIVE_LEN*(1 - 1/rel_num**2)
    part *= similarity(msg.text, hmsg.text, min_eff_len)**2

    if same_user(msg.id, hmsg.id):
        part = max(SCORE_MIN_SELF, part)
    else:
        part *= SCORE_MUL_OTHER

    part *= SCORE_MUL_10MSG**(rel_num/10.0)

    tdif = msg.time - hmsg.time
    part *= SCORE_MUL_HOUR**(tdif/3600.0)

    tmin = SCORE_POLE_SEC/(SCORE_POLE_MAX - 1)
    part *= (1 + SCORE_POLE_SEC/max(tmin, tdif))

    return part

def same_user(id1, id2):
    return id1.host == id2.host and \
           (id1.user == id2.user or id1.user[:1] == id2.user[:1] == '~')

WORD_RE = re.compile(r'(\w+)', re.U)
def similarity(str1, str2, min_eff_len):
    str1w, str2w = WORD_RE.split(str1), WORD_RE.split(str2)
    lcs_len = sum(len(w) for w in longest_common_substring(str1w, str2w))
    ratio = float(lcs_len+1)/(max(len(str1), len(str2), min_eff_len) + 1)
    return ratio

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
