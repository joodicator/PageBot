from collections import defaultdict
import re

from untwisted.magic import sign

import util
link, install, uninstall = util.LinkSet().triple()

channels = defaultdict(list)

def strip_names(names):
    return [re.sub(r'^[+%@~^]', '', n) for n in names]

def names(bot, chan):
    return util.mcall('channel.names', bot, chan.lower())

@link('channel.names')
def h_names(bot, chan):
    bot.send_cmd('NAMES %s' % chan)


@link('353')
def h_rpl_namereply(bot, _1, _2, _3, chan, names):
    channels[chan] += re.findall(r'\S+', names)


@link('366')
def h_rpl_endofnames(bot, _1, _2, chan, *args):
    yield sign(('channel.names', bot, chan.lower()), channels[chan])
    del channels[chan]
