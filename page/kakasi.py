#===============================================================================
import re

import util
import message

import kakasi_lib

#===============================================================================
link, install, uninstall = util.LinkSet().triple()

with open('conf/kakasi.txt') as file:
    auto_targets = set(re.findall(r'\S+', file.read().lower()))

#===============================================================================
@link('MESSAGE')
def h_message(bot, id, target, msg):
    if (target and target.lower()) not in auto_targets: return
    if kakasi_lib.is_ja(msg): kakasi(bot, id, target, msg)

#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('romaji TEXT',
    'Converts Japanese characters to romaji.')

@link(('HELP', 'romaji'))
def h_help_romaji(bot, reply, args):
    reply('romaji TEXT',
    'Shows the Hepburn romanisation(s) of Japanese characters occurring in TEXT,'
    ' according to KAKASI (http://kakasi.namazu.org).')

@link('!romaji')
def h_romaji(bot, id, target, args, full_msg):
    kakasi(bot, id, target, args)

#===============================================================================
def kakasi(bot, id, target, msg):
    reply = '<%s> %s' % (id.nick, kakasi_lib.kakasi(msg))
    message.reply(bot, id, target, reply, prefix=False)
