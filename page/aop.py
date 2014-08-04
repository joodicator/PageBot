import re
import random
from collections import defaultdict

from untwisted.magic import sign

import util
import runtime
import channel

link, link_install, uninstall = util.LinkSet().triple()

def install(bot):
    from control import AlreadyInstalled
    for dep in 'channel',:
        try: __import__(dep).install(bot)
        except AlreadyInstalled: pass
    link_install(bot)

CONF_PATH = 'conf/aop.txt'
DELAY_BASE_S = 6
DELAY_RAND_S = 3

#===============================================================================
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    if not has_aop_in(id, chan): return
    yield runtime.sleep(DELAY_BASE_S + random.uniform(0, DELAY_RAND_S))
    give_op_in(bot, id, chan)

#===============================================================================
@link('HELP')
def h_help(bot, reply, *args):
    reply('update', 'Enforce your automatic channel modes.')

@link(('HELP', 'update'))
def h_help_update(bot, reply, *args):
    reply('update',
    'If you have any automatic channel modes (such as auto-op) configured with'
    ' the bot for this channel, and your identity can be verified, this command'
    ' will immediately set those modes.')

@link('!update')
def h_update(bot, id, target, args, full_msg):
    if target and has_aop_in(id, target):
        give_op_in(bot, id, target)

#===============================================================================
def give_op_in(bot, id, chan):
    bot.send_cmd('MODE %s +o %s' % (chan, id.nick))

def has_aop_in(id, chan, conf=None):
    if conf is None: conf = read_conf()
    id_str = '%s!%s@%s' % tuple(id)
    for mask in conf.get(chan.lower(), []):
        try: mask = re.compile(util.wc_to_re(mask), flags=re.I)
        except re.error: continue
        if not mask.match(id_str): continue
        return True
    return False

def read_conf():
    conf = defaultdict(list)
    chans = None
    with open('conf/aop.txt') as file:
        for line in file:
            line = re.sub(r'--.*', r'', line).strip().lower()
            if not line: continue
            if line.startswith('#'):
                chans = line.split()
                continue
            for chan in chans:
                conf[chan].append(line)
    return conf
