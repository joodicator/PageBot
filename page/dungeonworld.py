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
    rolls = filter(lambda (f,m,t,i,r): t==target, all_rolls)

    nick_move, nick_fail = Counter(), Counter()
    for (f,m,t,(n,u,h),r) in rolls:
        nick_fail[n] += f
        nick_move[n] += m

    if not nick_fail: return reply('Missed rolls: none.')
    
    nicks_text = ', '.join(
        '\2%s: %d\2 of %d' % (n, f, nick_move[n])
        for (n,f) in nick_fail.iteritems())
    rolls_text = ''.join(
        '%s (%d/%d): %s\n' % (n, f, m, r)
        for (f,m,t,(n,u,h),r) in rolls if f)
    time = datetime.now().strftime('%Y-%m-%d %H:%M')
    rolls_url = pastebin.post(
        rolls_text,
        paste_expire    = pastebin.E_1WEEK,
        paste_name      = '%s %s Missed Rolls %s' % (bot.nick, target, time))

    reply('Missed rolls (estimated): %s. Full list: <%s>.'
        % (nicks_text, rolls_url))

    all_rolls = filter(lambda r: r not in rolls, all_rolls)
    with open(LOG_FILE, 'w') as file:
        for roll in all_rolls: print(roll, file=file)

#-------------------------------------------------------------------------------
@link('DICE_ROLLS')
def h_dice_rolls(bot, id, target, rolls, result_msg):
    move_rolls = filter(lambda ((d,s,a),r): (d,s) == (2,6), rolls)
    fail_rolls = filter(lambda (t,r): r < 7, move_rolls)
    if not move_rolls or not target: return
    with open(LOG_FILE, 'a') as file:
        print((
            len(fail_rolls),
            len(move_rolls),
            target,
            tuple(id),
            result_msg
        ), file=file)
