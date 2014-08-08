import re
import random
from collections import defaultdict

from untwisted.magic import sign

import util
import runtime
import channel
import identity

link, install, uninstall = util.LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'channel', 'identity')

CONF_PATH = 'conf/aop.txt'
DELAY_BASE_S = 6
DELAY_RAND_S = 3

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

conf = read_conf()

#===============================================================================
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    has_aop = yield has_aop_in(bot, id, chan)
    if not has_aop: return
    yield delayed_op_in(bot, [id.nick], chan)

@link('NAMES_SYNC')
def h_names_sync(bot, chan, nicks, *args):
    aop_nicks = []
    for nick in nicks:
        if nick.lower() == bot.nick.lower(): continue
        id = yield identity.get_id(bot, nick)
        has_aop = yield has_aop_in(bot, id, chan)
        if not has_aop: continue
        aop_nicks.append(nick)
    yield delayed_op_in(bot, aop_nicks, chan)

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
def h_update(bot, id, chan, args, full_msg):
    if not chan: return
    has_aop = yield has_op_in(bot, id, chan)
    if not has_aop: return
    yield give_op_in(bot, id, chan)

#===============================================================================
@util.mfun(link, 'aop.has_aop_in')
def has_aop_in(bot, id, chan, ret):
    id_str = '%s!%s@%s' % tuple(id)
    for op in conf.get(chan.lower(), []):
        if '!' in op or '@' in op:
            # Match against a nick!user@host with wildcards.
            try:
                op = re.compile(util.wc_to_re(mask), flags=re.I)
            except re.error:
                continue
            if op.match(id_str):
                yield ret(True)
                return
        else:
            # Match against an access name, according to 'identity'.
            access = yield identity.check_access(bot, id, op)
            if access:
                yield ret(True)
                return

    yield ret(False)

@util.msub(link, 'aop.delayed_op_in')
def delayed_op_in(bot, nicks, chan):
    yield runtime.sleep(DELAY_BASE_S + random.uniform(0, DELAY_RAND_S))
    yield give_op_in(bot, nicks, chan)

@util.msub(link, 'aop.give_op_in')
def give_op_in(bot, nicks, chan):
    umodes = channel.umode_channels.get(chan.lower(), dict())
    nicks = [nick for nick in nicks if 'o' not in umodes.get(nick.lower(), '')]

    max_modes = 3 if 'MODES' not in bot.isupport else \
                None if not bot.isupport['MODES'] else \
                int(bot.isupport['MODES'])

    while nicks:
        op_cmd, op_nicks = '', []
        while nicks and len(op_cmd) < 400 and len(op_nicks) < max_modes:
            op_nicks.append(nicks.pop(0))
            op_cmd = 'MODE %s +%s %s' % (
                chan, 'o'*len(op_nicks), ' '.join(op_nicks))
        bot.send_cmd(op_cmd)
