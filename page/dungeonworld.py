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
@link('!missed-rolls')
def h_missed_rolls(bot, id, target, args, full_msg):
    reply = lambda m: message.reply(bot, id, target, m, prefix=False, wrap=True)
    try: all_rolls = util.read_list(LOG_FILE)
    except IOError: all_rolls = []
    rolls = filter(lambda (f,m,t,i,r): t==target, all_rolls)

    nick_case = dict()
    nick_move, nick_fail = Counter(), Counter()
    for (f,m,t,(n,u,h),r) in rolls:
        n_key = n.lower()
        if n_key not in nick_case: nick_case[n_key] = n
        nick_fail[n_key] += f
        nick_move[n_key] += m

    if not nick_fail: return reply('Missed rolls: none.')
    
    nicks_text = ', '.join(
        '\2%s: %d\2 of %d' % (nick_case[n], f, nick_move[n])
        for (n,f) in nick_fail.iteritems())
    reply_msg = 'Missed rolls (estimated): %s.' % nicks_text

    rolls_text = ''.join(
        '%s (%d/%d): %s\n' % (nick_case[n.lower()], f, m, r)
        for (f,m,t,(n,u,h),r) in rolls if f)
    if rolls_text:
        time = datetime.now().strftime('%Y-%m-%d %H:%M')
        rolls_url = pastebin.post(
            rolls_text,
            paste_expire = pastebin.E_1MONTH,
            paste_name   = '%s %s Missed Rolls %s' % (bot.nick, target, time))
        reply_msg += ' Full list: <%s>.' % rolls_url

    reply(reply_msg)

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
