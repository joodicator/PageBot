from __future__ import print_function
from collections import Counter
from datetime import datetime

from util import multi
import channel
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
    reply('missed-rolls', 'Gives a tally of missed 2d6+N rolls.')

@link(('HELP', 'missed-rolls'))
def h_help_missedrolls(bot, reply, args):
    reply('missed-rolls',
    'Gives a tally of dice rolls of the form 2d6+N, b2(Md6+N) or w2(Md6+N)'
    ' whose result was less than 7, grouped by the nick who made the roll,'
    ' since the last time this command was invoked. This is useful for'
    ' playing Dungeon World RPGs in IRC. See also: \2!view-missed-rolls\2,'
    ' \2!insert-missed-roll\2, \2!delete-missed-roll\2,'
    ' \2!clear-missed-rolls\2.')

@link('!missed-rolls')
def h_missed_rolls(bot, id, target, args, full_msg):
    if target is None:
        message.reply(bot, id, target,
            'Error: this command may not be used by PM; however, see'
            ' \2!help view-missed-rolls\2 for a version which can.')
    elif args:
        message.reply(bot, id, target,
            'Error: this command does not accept any parameters. Perhaps you'
            ' meant \2!view-missed-rolls\2.')
    else:
        def reply(msg):
            message.reply(bot, id, target, msg, prefix=False, wrap=True)
        yield show_missed_rolls(bot, target, reply, delete=True)

#-------------------------------------------------------------------------------
@link(('HELP', 'view-missed-rolls'))
def h_help_insert_missed_roll(bot, reply, args):
    reply('view-missed-rolls [CHANNEL]',
    'Gives a tally of missed dice rolls in CHANNEL, or in the current channel'
    ' if not specified, as per \2!missed-rolls\2, without deleting any rolls'
    ' from the record. May be used by PM.')

@link('!view-missed-rolls')
def h_view_missed_rolls(bot, id, target, args, full_msg):
    if args:
        nicks = map(str.lower, channel.track_channels[args.lower()])
        if id.nick.lower() not in nicks:
            message.reply(bot, id, target,
                'Error: you must be in "%s" to view its rolls.' % args)
            return
        chan = args
        local = False
    elif not target:
        message.reply(bot, id, target,
            'Error: you must specify a channel. See'
            ' \2!help view-missed-rolls\2 for correct usage.')
        return
    else:
        chan = target
        local = True

    def reply(msg):
        message.reply(bot, id, target, msg, prefix=False, wrap=True)
    yield show_missed_rolls(bot, chan, reply, delete=False, local=local)

#-------------------------------------------------------------------------------
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
    
    append_roll((1, 1, target, r_id, label))
    reply('Inserted 1 missed roll by %s.' % r_id[0])

#-------------------------------------------------------------------------------
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

    all_rolls = read_rolls()
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
    replace_rolls(all_rolls)
    reply('Deleted %d missed roll%s by %s%s.' % (
        failed, 's' if failed != 1 else '', r_id[0], label and ': "%s"' % label))

#-------------------------------------------------------------------------------
@link(('HELP', 'clear-missed-rolls'))
def h_help_insert_missed_roll(bot, reply, args):
    reply('clear-missed-rolls',
    'Deletes all dice rolls recorded in this channel for the purposes of'
    ' \2!missed-rolls\2.')

@link('!clear-missed-rolls')
def h_clear_missed_rolls(bot, id, target, args, full_msg):
    if not target: return
    if args:
        message.reply(bot, id, target,
            'Error: this command does not accept any parameters.'
            ' See \2!help clear-missed-rolls\2 for correct usage.')
        return

    all_rolls = read_rolls()
    move_count, fail_count, new_rolls = 0, 0, []
    for roll in all_rolls:
        (r_fail, r_move, r_target, _, _) = roll
        if r_target.lower() == target.lower():
            move_count += r_move
            fail_count += r_fail
        else:
            new_rolls.append(roll)        

    replace_rolls(new_rolls)
    message.reply(bot, id, target,
        'Deleted %d dice rolls, of which %d were missed.'
        % (move_count, fail_count))

#-------------------------------------------------------------------------------
@util.msub(link, 'dungeonworld.show_missed_rolls')
def show_missed_rolls(
    bot, target, reply, delete=True, all_rolls=True, local=True
):
    all_rolls = read_rolls()
    rolls = filter(lambda (f,m,t,i,r): t.lower()==target.lower(), all_rolls)

    nick_case = dict()
    nick_move, nick_fail = Counter(), Counter()
    for (f,m,t,(n,u,h),r) in rolls:
        n_key = n.lower()
        if n_key not in nick_case: nick_case[n_key] = n
        nick_fail[n_key] += f
        nick_move[n_key] += m

    reply_msg = 'Missed rolls%s (estimated): ' % ('' if local else
        ' in %s' % channel.capitalisation.get(target, target),)

    if nick_fail:
        nicks_text = ', '.join(
            '\2%s: %d\2 of %d' % (nick_case[n], f, nick_move[n])
            for (n,f) in nick_fail.iteritems())
        reply_msg += '%s.' % nicks_text
    else:
        reply_msg += 'none.'

    if nick_move and (all_rolls or nick_fail):
        rolls_text = ''.join(
            '%s (%d/%d)%s\n' % (nick_case[n.lower()], f, m, r and ': %s' % r)
            for (f,m,t,(n,u,h),r) in rolls if all_rolls or f)
        if rolls_text:
            time = datetime.now().strftime('%Y-%m-%d %H:%M')
            rolls_url = pastebin.post(
                strip_irc(rolls_text),
                paste_expire=pastebin.E_1MONTH,
                paste_name='%s %s Missed Rolls %s' % (bot.nick, target, time))
            reply_msg += ' Full list: <%s>.' % rolls_url

    reply(reply_msg)

    if delete:
        all_rolls = filter(lambda r: r not in rolls, all_rolls)
        replace_rolls(all_rolls)

#-------------------------------------------------------------------------------
@link('DICE_ROLLS')
def h_dice_rolls(bot, id, target, rolls, result_msg):
    move_rolls = filter(is_move_roll, rolls)
    fail_rolls = filter(lambda (t,r): r < 7, move_rolls)
    if not move_rolls or not target: return
    append_roll((
        len(fail_rolls),
        len(move_rolls),
        target,
        tuple(id),
        result_msg))

def is_move_roll(((d,s,a), r)):
    dice, drop_low, drop_high = d if isinstance(d, tuple) else (d, 0, 0)
    return (dice - drop_low - drop_high, s) == (2, 6)

def read_rolls():
    return util.read_list(LOG_FILE, default=True)

def replace_rolls(rolls):
    with open(LOG_FILE, 'w') as file:
        for roll in rolls: print(roll, file=file)

def append_roll(roll):
    with open(LOG_FILE, 'a') as file:
        print(roll, file=file)

#===============================================================================
def strip_irc(str):
    return re.sub(r'[\02\31\22\15]|\03\d{,2}(,\d{1,2})?', '', str)
