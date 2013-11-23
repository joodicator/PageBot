import re
import random

import util
import message

link, install, uninstall = util.LinkSet().triple()

MAX_DICE = 2**16
MAX_SIDES = 2**32

@link('HELP')
def h_help(bot, reply, args):
    reply('dice MdN [...]',
    'Simulates the rolling of dice.')

@link(('HELP', 'dice'))
@link(('HELP', 'roll'))
@link(('HELP', 'd'))
@link(('HELP', 'r'))
def h_help_roll(bot, reply, args):
    reply('dice MdN [MdN ...]',
    'Simulates one or more dice rolls, giving the total result of each roll.'
    ' Each roll is specified as "MdN", where M is the number of dice, N is'
    ' the number of sides on each die, and N and M are non-negative integers.'
    ' The value of a 1dN roll is uniformly distributed between 1 and N; the'
    ' value of an MdN roll is the sum of M rolls of 1dN, and is non-uniformly'
    ' distributed between M and M*N.')
    reply('',
    'For example, "dice 2d6" simulates rolling two 6-sided dice at once,'
    ' and "dice 1d6 1d6" simulates rolling two 6-sided dice separately.'
    ' Instead of "dice", the command names "roll", "r", or "d" may be used.')

@link('!roll')
@link('!dice')
@link('!r')
@link('!d')
def h_roll(bot, id, target, args, full_msg):
    reply = lambda msg: message.reply(bot, id, target, msg)
    rolls = []
    for arg in args.split():
        match = re.match(r'(\d+)d(\d+)$', arg, re.I)
        if not match: return reply(
            'Invalid syntax: "%s". See "help dice" for more information.' % arg)
        dice = int(match.group(1))
        sides = int(match.group(2))
        if dice > MAX_DICE or sides > MAX_SIDES: return reply(
            'Error: You may not use more than %d dice,'
            ' or %d sides per dice, per roll.' % (MAX_DICE, MAX_SIDES))
        rolls.append(sum(random.randint(1, sides) for i in xrange(dice)))
    if rolls:
        reply(' '.join(str(roll) for roll in rolls))
    else:
        reply('Error: You must specify at least one dice roll.'
        ' See "help dice" for more information.')
