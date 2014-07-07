from __future__ import print_function
from collections import Counter
from datetime import datetime

from util import multi
import pastebin
import message
import util
import re

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
    rolls = filter(lambda (f,m,t,i,r): t.lower()==target.lower(), all_rolls)

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
        '%s (%d/%d)%s\n' % (nick_case[n.lower()], f, m, r and ': %s' % r)
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
@link('HELP')
def h_help(bot, reply, args):
    reply('insert-missed-roll [NICK [COMMENT ...]]',
    'Inserted a synthetic missed dice roll.')

@link(('HELP', 'insert-missed-roll'))
def h_help_insert_missed_roll(bot, reply, args):
    reply('insert-missed-roll [NICK [COMMENT ...]] [!insert-missed-roll ...]',
    'Inserts into the record of dice rolls an entry meaning that NICK (or the'
    ' nick giving the command) missed a single roll according to'
    ' "missed-rolls".')

@link('!insert-missed-roll')
@multi('!insert-missed-roll', limit=4, prefix=False)
def h_insert_missed_roll(bot, id, target, args, full_msg, reply):
    if not target: return

    nick, label = re.match(r'(\S*)\s*(.*)', args).groups()
    r_id = (nick,'*','*') if nick else id
    label = label or '(inserted by %s)' % id.nick
    
    with open(LOG_FILE, 'a') as file:
        print((1,1,target,r_id,label), file=file)

    reply('Inserted 1 missed roll by %s.' % r_id[0])

#-------------------------------------------------------------------------------
@link('HELP')
def h_help(bot, reply, args):
    reply('delete-missed-roll [NICK]',
    'Deletes the last missed dice roll.')

@link(('HELP', 'delete-missed-roll'))
def h_help_insert_missed_roll(bot, reply, args):
    reply('delete-missed-roll [NICK] [!delete-missed-roll ...]',
    'Deletes from the record of dice rolls the last roll by NICK (or, if not'
    ' specified, by anyone) which was missed according to "missed-rolls".')

@link('!delete-missed-roll')
@multi('!delete-missed-roll', limit=4, prefix=False)
def h_delete_missed_roll(bot, id, target, args, full_msg, reply):
    if not target: return
    nick = re.match(r'\S*', args).group()

    try: all_rolls = util.read_list(LOG_FILE)
    except IOError: all_rolls = []

    delete_index = None
    for index in range(len(all_rolls)):
        (failed,_,r_target,(r_nick,_,_),_) = all_rolls[index]
        if not failed: continue
        if r_target.lower() != target.lower(): continue
        if nick and r_nick.lower() != nick.lower(): continue
        delete_index = index

    if delete_index is None: return reply(
        'There are no missed rolls%s to delete.' % (nick and ' by "%s"' % nick))

    (_,_,_,r_id,label) = all_rolls.pop(delete_index)

    with open(LOG_FILE, 'w') as file:
        for roll in all_rolls:
            print(roll, file=file)

    reply('Deleted 1 missed roll by %s%s.'
        % (r_id[0], label and ': "%s"' % label))

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
