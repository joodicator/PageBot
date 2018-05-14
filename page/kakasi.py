#===============================================================================
import re

from untwisted.magic import sign

from channel import not_quiet
from runtime import later
import message
import util
import limit

import kakasi_lib

link, install, uninstall = util.LinkSet().triple()

#===============================================================================
'''
@link('MESSAGE')
@not_quiet()
def h_message(bot, id, target, msg):
    if limit.mark_activity(bot, id): return
    kakasi(bot, id, target or id.nick, msg, target is not None, auto=True)

@link('PROXY_MSG')
@not_quiet()
def h_proxy_message(
    bot, id, target, msg, no_kakasi=False, no_auto=False, **kwds
):
    if no_kakasi or no_auto: return
    kakasi(bot, id, target, msg, target.startswith('#'), auto=True, **kwds)
'''

#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('romaji TEXT',
    'Converts Japanese characters to romaji.')

@link(('HELP', 'romaji'))
@link(('HELP', 'rj'))
def h_help_romaji(bot, reply, args):
    reply('romaji TEXT')
    reply('rj TEXT',
    'Shows the Hepburn romanisation(s) of Japanese characters occurring in TEXT,'
    ' according to KAKASI <http://kakasi.namazu.org>. The command prefix may be'
    ' omitted, leaving just TEXT, if the majority of TEXT is Japanese.')

@link('!romaji')
@link('!rj')
def h_romaji(bot, id, target, args, full_msg):
    kakasi(bot, id, target or id.nick, args, target is not None)

#===============================================================================
def kakasi(bot, id, target, msg, prefix=True, auto=False, **kwds):
    if auto and not kakasi_lib.is_ja(msg): return
    raw_reply = kakasi_lib.kakasi(msg)
    if auto and len(raw_reply) > 200: return
    reply = ('<%s> %s' % (id.nick, raw_reply)) if prefix and id else raw_reply
    bot.send_msg(target, reply)
    bot.drive('runtime.later', sign(
        'PROXY_MSG', bot, id, target, raw_reply, **dict(kwds, no_kakasi=True)))

