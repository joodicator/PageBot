import re
import random

from untwisted.magic import sign

import util
import message

link, install, uninstall = util.LinkSet().triple()

DEFAULT_ROLL    = 2, 6, 0
MAX_ROLL        = 99, 9999, 99999999

#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('dice [MdN[+K|-K] ...]',
    'Simulates the rolling of dice.')

#===============================================================================
@link(('HELP', 'dice'), ('HELP', 'roll'), ('HELP', 'd'), ('HELP', 'r'))
def h_help_roll(bot, reply, args):
    reply('dice [MdN[+K|-K] ...]',
    'Simulates one or more dice rolls, listing for each roll its total result,'
    ' as well as the value of each individual die. '
    'Each roll is specified as "MdN", "MdN+K", or "MdN-K", where M is the'
    ' number of dice, N is the number of sides on each die, and K or -K is an'
    ' integer added to the result. '
    'The value of a 1dN roll is uniformly distributed between 1 and N;'
    ' the value of an MdN roll is the sum of M rolls of 1dN.')
    reply('',
    '"dN" may be used as shorthand for "1dN", "+K" or "-K" for "2d6+K" or'
    ' "2d6-K", and "dice" for "dice 2d6". '
    'For example, "dice 2d6" (or just "dice") simulates rolling two 6-sided'
    ' dice at once, and "dice 1d6 2d6-1" (or "dice d6 -1") simulates two'
    ' separate rolls as specified. '
    'Finally, instead of "dice", the command names "roll", "r", or "d" may be'
    ' used. '
    'Any other text is repeated unchanged in the command\'s output.')

#===============================================================================
@link('!roll', '!r', '!dice', '!d')
def h_roll(bot, id, target, args, full_msg):
    class UserError(Exception):
        pass

    rolls = []

    def check_roll(dice=None, sides=None, add=None):
        if sides is not None and sides == 0: raise UserError(
            '"d0" does not make sense - the number of sides must be positive.')
        if (dice and dice > MAX_ROLL[0] or
            sides and sides > MAX_ROLL[1] or
            add and abs(add) > MAX_ROLL[2]
        ): raise UserError(
            'No more than %d dice, %d sides per die, or %s units added or'
            ' subtracted are permitted per roll.' % MAX_ROLL)

    def roll_sub(match):
        dice = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        add = int(match.group(3)) if match.group(3) else 0
        return do_roll_str(dice, sides, add)

    def add_sub(match):
        dice, sides, add = DEFAULT_ROLL
        add += int(match.group(1))
        return do_roll_str(dice, sides, add)

    def do_roll_str(dice, sides, add):
        check_roll(dice, sides, add)
        rstr, rint = roll_str_int(dice, sides, add)
        rolls.append(((dice, sides, add), rint))
        return rstr
    
    try:
        msg = re.sub(r'(?:^|(?<=\W))([+-]\d+)\b', add_sub, args)
        msg = re.sub(r'\b(\d*)[dD](\d+)([+-]\d+)?\b', roll_sub, msg)
        if msg == args:
            msg = '%s %s' % (do_roll_str(*DEFAULT_ROLL), args)
            msg = '(%s) %s' % (roll_str_spec(*DEFAULT_ROLL), msg)
        if len(msg) > 400: msg = '%s(...)' % msg[:395]
        yield sign('DICE_ROLLS', bot, id, target, rolls, msg)
        message.reply(bot, id, target, msg)
    except UserError as e:
        message.reply(bot, id, target, 'Error: %s' % e.message)

#===============================================================================
def roll_str_int(dice, sides, add):
    rolls = roll_list(dice, sides)
    rint = sum(rolls) + add
    rstr = '%s%s%s' % (
        '\2%s\2' % rint,
        '=%s' % '+'.join(map(str, rolls)) if add or dice>1 else '',
        '(%+d)' % add if add else '')
    return (rstr, rint)

#===============================================================================
def roll_str_spec(dice, sides, add):
    return '%sd%d%s' % (
        str(dice) if dice != 1 else '',
        sides,
        '%+d' % add if add else '')

#===============================================================================
def roll_list(dice, sides):
    return [random.randint(1, sides) for i in xrange(dice)]
