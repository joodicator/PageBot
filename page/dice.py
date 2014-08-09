import re
import random

from untwisted.magic import sign

import util
import message
import modal

link, install, uninstall = util.LinkSet().triple()

MAX_ROLL = 99, 9999, 99999999

#===============================================================================
@link('HELP*')
def h_help(bot, reply, args):
    reply('roll [MdN[+K|-K] ...]',
    'Simulates the rolling of dice.')

#===============================================================================
@link(('HELP', 'roll'), ('HELP', 'r'))
def h_help_roll(bot, reply, args):
    reply('roll MdN[+K|-K] ...',
    'Simulates one or more dice rolls. '
    'A roll is specified as "MdN", "MdN+K", or "MdN-K", where M is the number'
    ' of dice, N is the number of sides of each die, and K or -K is an integer'
    ' added to the result. '
    'Rolls may be annotated with other text, which is repeated in the results. '
    'The shorthand "!r" may be used instead of "!roll".')

#===============================================================================
@link('!r', '!d')
@modal.when_mode(None)
def h_roll_abbrev(*args):
    return h_roll(*args)

@link('!roll', '!dice')
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

    def do_roll_str(dice, sides, add):
        check_roll(dice, sides, add)
        rstr, rint = roll_str_int(dice, sides, add)
        rolls.append(((dice, sides, add), rint))
        return rstr
    
    try:
        msg = re.sub(r'\b(\d*)[dD](\d+)([+-]\d+)?\b', roll_sub, args)
        if msg == args: raise UserError('No dice rolls specified.')
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
