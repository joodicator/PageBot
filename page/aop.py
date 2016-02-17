import re
import random
import traceback
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
    try:
        with open('conf/aop.txt') as file:
            for line in file:
                line = re.sub(r'--.*', r'', line).strip().lower()
                if not line: continue
                if line.startswith('#'):
                    chans = line.split()
                    continue
                for chan in chans:
                    conf[chan].append(line.strip())
    except IOError:
        traceback.print_exc()
    return conf

conf = read_conf()

#===============================================================================
@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    yield maybe_aop(bot, [id], chan, delay=True)

@link('CHAN_MODE')
def h_chan_mode(bot, src, chan, modes):
    for (pm, mchar, marg) in modes:
        if pm == '+' and mchar in 'oh' and marg.lower() == bot.nick.lower():
            yield maybe_aop_chan(bot, chan)
            break

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
    yield maybe_aop(bot, [id], chan)

#===============================================================================
@util.msub(link, 'aop.maybe_aop')
def maybe_aop(bot, ids, chan, delay=False):
    aop_nicks = []
    for nick_or_id in ids:
        if isinstance(nick_or_id, tuple):
            id = nick_or_id
        else:
            id = yield identity.get_id(bot, nick_or_id)
        if id is not None:
            has_aop = yield has_aop_in(bot, id, chan)
        else:
            has_aop = False
        if has_aop: aop_nicks.append(id.nick)

    if delay:
        yield delayed_op_in(bot, aop_nicks, chan)
    else:
        yield give_op_in(bot, aop_nicks, chan)

@util.msub(link, 'aop.maybe_aop_chan')
def maybe_aop_chan(bot, chan, delay=False):
    names = yield channel.names(bot, chan, include_prefix=False)
    yield maybe_aop(bot, names, chan, delay=delay)

@util.mfun(link, 'aop.has_aop_in')
def has_aop_in(bot, id, chan, ret):
    id_str = '%s!%s@%s' % tuple(id)
    for op in conf.get(chan.lower(), []):
        if '!' in op or '@' in op:
            # Match against a nick!user@host with wildcards.
            try:
                op = re.compile(util.wc_to_re(op), flags=re.I)
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
        while (nicks and len(op_cmd) < 400
        and (max_modes is None or len(op_nicks) < max_modes)):
            op_nicks.append(nicks.pop(0))
            op_cmd = 'MODE %s +%s %s' % (
                chan, 'o'*len(op_nicks), ' '.join(op_nicks))
        bot.send_cmd(op_cmd)
