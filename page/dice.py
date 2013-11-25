import re
import random

import util
import message

link, install, uninstall = util.LinkSet().triple()

DEFAULT_ROLL    = 2, 6
MAX_DICE        = 64
MAX_SIDES       = 999

@link('HELP')
def h_help(bot, reply, args):
    reply('dice MdN [...]',
    'Simulates the rolling of dice.')

#===============================================================================
@link(('HELP', 'dice'))
@link(('HELP', 'roll'))
@link(('HELP', 'd'))
@link(('HELP', 'r'))
def h_help_roll(bot, reply, args):
    reply('dice [M]dN[+K|-K] [[M]dN[+K|-K] ...]',
    'Simulates one or more dice rolls, listing for each roll the total result,'
    ' as well as the value of each individual die. '
    'Each roll is specified as "MdN", "MdN+K", or "MdN-K", where M is the'
    ' number of dice, N is the number of sides on each die, and K or -K is an'
    ' integer added to the result. '
    'The value of a 1dN roll is uniformly distributed between 1 and N;'
    ' the value of an MdN roll is the sum of M rolls of 1dN.')
    reply('',
    '"dN" may be used as shorthand for "1dN", and "dice" for "dice 2d6". For'
    ' example, "dice 2d6" (or just "dice") simulates rolling two 6-sided dice at'
    ' once, and "dice 1d6 1d6" (or "dice d6 d6") simulates rolling two 6-sided'
    ' dice separately. Finally, instead of "dice", the command names "roll",'
    ' "r", or "d" may be used.')

@link('!roll')
@link('!dice')
@link('!r')
@link('!d')
def h_roll(bot, id, target, args, full_msg):
    reply = lambda msg: message.reply(bot, id, target, msg)
    total_dice = 0
    rolls = []
    for arg in args.split():
        match = re.match(r'(\d*)d(\d+)([+-]\d+)?$', arg, re.I)
        if not match: return reply(
            'Invalid syntax: "%s". See "help dice" for more information.' % arg)
        dice = int(match.group(1) or '1')
        sides = int(match.group(2))
        addend = int(match.group(3) or '0')
        if not sides: return reply('Error: "d0" does not make sense'
            ' - the number of sides must be positive.')
        total_dice += dice
        if total_dice > MAX_DICE or sides > MAX_SIDES: return reply(
            'Error: You may not use more than %d sides per die, nor'
            ' roll more than %d dice in total.' % (MAX_SIDES, MAX_DICE))
        rolls.append((dice, sides, addend))
    
    if rolls:
        reply('%s.' % '; '.join(roll_str(*roll) for roll in rolls))
    else:
        dice, sides = DEFAULT_ROLL
        reply('(%dd%d) %s.' % (dice, sides, roll_str(dice, sides, 0)))

def roll_str(dice, sides, add):
    rolls = roll_list(dice, sides)
    head = '\2%s\2' % (sum(rolls) + add)
    body = '=%s' % '+'.join(map(str, rolls)) if add or dice>1 else ''
    tail = '(%+d)' % add if add else ''
    return '%s%s%s' % (head, body, tail)

def roll_list(dice, sides):
    return [random.randint(1, sides) for i in xrange(dice)]
