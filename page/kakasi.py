#===============================================================================
import re

from channel import not_quiet
import message
import util
import limit

import kakasi_lib

link, install, uninstall = util.LinkSet().triple()

#===============================================================================
@link('MESSAGE')
@not_quiet()
def h_message(bot, id, target, msg):
    if kakasi_lib.is_ja(msg):
        if limit.mark_activity(bot, id):
            return
        kakasi(bot, id, target, msg, target is not None)

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
    kakasi(bot, id, target, args, prefix=target is not None)

#===============================================================================
def kakasi(bot, id, target, msg, prefix=True):
    reply = kakasi_lib.kakasi(msg)
    if prefix: reply = '<%s> %s' % (id.nick, reply)
    message.reply(bot, id, target, reply, prefix=False)
