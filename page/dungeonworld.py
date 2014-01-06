from __future__ import print_function
from collections import Counter
from datetime import datetime

import pastebin
import message
import util

link, install, uninstall = util.LinkSet().triple()

MAX_MISSED_ROLLS = 8
LOG_FILE = 'state/dungeonworld_rolls.txt'

#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('missed-rolls',
    'Gives a tally of missed 2d6+N rolls.')

#-------------------------------------------------------------------------------
@link(('HELP', 'missed-rolls'))
def h_help_missedrolls(bot, reply, args):
    reply('missed-rolls',
    'Gives a tally of dice rolls of the form 2d6+N whose value was less than 7,'
    ' grouped by the nick who made the roll, since the last time this command'
    ' was invoked.')

#-------------------------------------------------------------------------------
@link('!missed-rolls', '!failed-rolls')
def h_missed_rolls(bot, id, target, args, full_msg):
    reply = lambda m: message.reply(bot, id, target, m, prefix=False, wrap=True)
    try: all_rolls = util.read_list(LOG_FILE)
    except IOError: all_rolls = []
    rolls = filter(lambda (f,t,i,r): t==target, all_rolls)

    if not rolls: return reply('Missed rolls: none.')

    nicks = Counter()
    for (f,t,(n,u,h),r) in rolls: nicks[n] += f

    nicks_text = ', '.join('\2%s: %d\2' % i for i in nicks.iteritems())
    rolls_text = ''.join('%s (%d): %s\n' % (n,f,r) for (f,t,(n,u,h),r) in rolls)
    time = datetime.now().strftime('%Y-%m-%d %H:%M')
    rolls_url = pastebin.post(
        rolls_text,
        paste_expire    = pastebin.E_1WEEK,
        paste_name      = '%s %s Missed Rolls %s' % (bot.nick, target, time))

    reply('Missed rolls: %s. Full list: <%s>.' % (nicks_text, rolls_url))

    all_rolls = filter(lambda r: r not in rolls, all_rolls)
    with open(LOG_FILE, 'w') as file:
        for roll in all_rolls: print(roll, file=file)

#-------------------------------------------------------------------------------
@link('DICE_ROLLS')
def h_dice_rolls(bot, id, target, rolls, result_msg):
    failed = len(filter(lambda ((d,s,a),r): (d,s)==(2,6) and r<7, rolls))
    if not (failed and target): return
    with open(LOG_FILE, 'a') as file:
        print((failed, target, tuple(id), result_msg), file=file)
