import re
import random
import math

from untwisted.magic import sign

import util
import message
import modal

link, install, uninstall = util.LinkSet().triple()

MAX_ROLL = 99, 9999, 99999999

#===============================================================================
@link('HELP*', ('BRIDGE', 'HELP*'))
def h_help(bot, reply, args):
    reply('roll MdN[+K|-K]', 'Simulates the rolling of dice.')

#===============================================================================
@link(('HELP', 'roll'), ('HELP', 'r'), bridge=False)
@link(('BRIDGE', 'HELP', 'roll'), ('BRIDGE', 'HELP', 'r'), bridge=True)
def h_help_roll(bot, reply, args, bridge):
    if args and int(args) == 2 and not bridge:
        reply('roll ... MdN[+K|-K] ...',
        'Simulates one or more dice rolls. A roll is specified as "MdN",'
        ' "MdN+K", or "MdN-K", where M is the number of dice, N is the number'
        ' of sides of each die, and K or -K is an integer added to the result.'
        ' Rolls may be annotated with other text, which is repeated in the'
        ' result. The shorthand "!r" may be used instead of "!roll".')
        reply('roll ... bJ(ROLL) ...\2 or \2!roll ... wJ(ROLL) ...',
        'Where ROLL is a dice roll of the form MdN, MdN+K or MdN-K, as'
        ' specified above, and J is a non-negative integer, this form discards'
        ' all but the J highest (in the case of bJ) or lowest (in the case of'
        ' wJ) individual dice out of the original M dice rolled. If J is'
        ' omitted, it it defaults to 1. Examples: "!roll w(2d8-1)" or'
        ' "!roll b2(3d6)".')
        reply('roll {[WEIGHT1:]ITEM1, [WEIGHT2:]ITEM2, ...}',
        'For each comma-separated list of items enclosed in curly braces,'
        ' chooses one item at random and replaces the list with that item.'
        ' Items are selected with probability proportional to their WEIGHT,'
        ' which can be specified as a positive number followed by a colon'
        ' before the item, or otherwise defaults to 1. Each item may contain'
        ' dice rolls, or further brace-delimited lists to be recursively'
        ' evaluated in the same way.')
    else:
        reply('roll MdN\2 or \2!roll MdN+K\2 or \2!roll MdN-K',
        'Simulates the rolling of M dice, each of which has N sides, giving'
        ' the sum of the individual results. Optionally, adds (for MdN+K) or'
        ' subtracts (for MdN-K) a value of K to or from the result. Example:'
        ' "!roll 2d6+1".' +
        (' For advanced features, see \2!help roll 2\2. See also: '
        '\2!help missed-rolls\2.' if not bridge else
        ' For advanced features, send \2!help roll 2\2 by IRC.'))

#===============================================================================
class UserError(Exception):
    pass

@link(('SIMPLE','!roll'), ('SIMPLE','!r'), action=False)
@link(('BRIDGE','!roll'), ('BRIDGE','!r'), action=False)
@link(('SIMPLE','ACTION','!roll'), ('SIMPLE','ACTION','!r'), action=True)
@link(('BRIDGE','ACTION','!roll'), ('BRIDGE','ACTION','!r'), action=True)
def h_roll(bot, name, target, args, reply, action):
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

    def keep_sub(match):
        bw = match.group('bw').lower()
        keep = int(match.group('keep')) if match.group('keep') else 1
        dice = int(match.group('dice')) if match.group('dice') else 1       
        sides = int(match.group('sides'))
        add = int(match.group('add')) if match.group('add') else 0

        if keep > dice: raise UserError(
            'It is not possible to keep %d out of %s dice rolls.'
            % (keep, dice))

        if bw == 'b':
            return do_roll_str(dice, sides, add, drop_low=dice-keep)
        elif bw == 'w':
            return do_roll_str(dice, sides, add, drop_high=dice-keep)

    def roll_sub(match):
        dice = int(match.group('dice')) if match.group('dice') else 1
        sides = int(match.group('sides'))
        add = int(match.group('add')) if match.group('add') else 0
        return do_roll_str(dice, sides, add)

    def do_roll_str(dice, sides, add, drop_low=0, drop_high=0):
        check_roll(dice, sides, add)
        rstr, rint = roll_str_int(dice, sides, add, drop_low, drop_high)
        if drop_low or drop_high:
            dice_spec = (dice, drop_low, drop_high)
        else:
            dice_spec = dice
        rolls.append(((dice_spec, sides, add), rint))
        return rstr

    try:
        msg = args
        msg = re.sub(
            r'\b(?P<bw>[bBwW])(?P<keep>\d*)'
            '\((?P<dice>\d*)[dD](?P<sides>\d+)(?P<add>[+-]\d+)?\)',
            keep_sub, msg)
        msg = re.sub(
            r'\b(?P<dice>\d*)[dD](?P<sides>\d+)(?P<add>[+-]\d+)?\b',
            roll_sub, msg)
        msg = expand_choices(msg)
        if msg == args: raise UserError(
            'No dice rolls or choices specified.'
            ' See \2!help roll 2\2 for correct usage.')
        if len(msg) > 400: msg = '%s(...)' % msg[:395]
        if target and target.startswith('#'):
            id = util.ID(name, '*', '*')
            yield sign('DICE_ROLLS', bot, id, target, rolls, msg)
        if action:
            reply('* %s %s' % (name, msg), prefix=False)
        else:
            reply(msg)
    except UserError as e:
        reply('Error: %s' % e.message)

#===============================================================================
def expand_choices(str):
    while True:
        match = re.search(r'\{(?P<items>[^{}]*)\}', str)
        if not match: break
        weight_sum = 0
        cum_weight_items = []

        for item in match.group('items').split(','):
            item = item.strip()
            pmatch = re.match(r'(?P<weight>\d*\.?\d+)\s*:\s*(?P<item>.*)', item)
            if pmatch:
                weight = float(pmatch.group('weight'))
                if weight <= 0: raise UserError('The weight "%s" is too small.'
                    % abbrev_middle(pmatch.group('weight')))
            if pmatch:
                item = pmatch.group('item')
            else:
                weight = 1
            weight_sum += weight
            cum_weight_items.append((weight_sum, item))

        if math.isinf(weight_sum): raise UserError(
            'The weights in "%s" are too large.' % abbrev_middle(match.group()))
        if math.isnan(weight_sum): raise UserError(
            'The weights in "%s" are invalid.' % abbrev_middle(match.group()))
        
        chosen_weight = random.uniform(0, weight_sum)
        for cum_weight, item in cum_weight_items:
            if chosen_weight <= cum_weight: break
        
        str = str[:match.start()] + item + str[match.end():]
    return str

#===============================================================================
ABBREV_MAX_LEN = 50
def abbrev_middle(str):
    if len(str) <= ABBREV_MAX_LEN: return str
    left_len = (ABBREV_MAX_LEN - 3)/2
    right_len = (ABBREV_MAX_LEN - 3) - left_len
    return str[:left_len] + '...' + str[-right_len:]

#===============================================================================
def roll_str_int(dice, sides, add, drop_low=0, drop_high=0):
    rolls = roll_list(dice, sides)
    drop = sorted(rolls)
    del drop[drop_low:dice-drop_high]
    rint = sum(rolls) + add - sum(drop)
    rstr = ''.join((
        '\2%s\2' % rint,
        '=%s' % '+'.join(map(str, rolls)) if add or dice>1 else '',
        ''.join('-%d' % r for r in drop),
        '(%+d)' % add if add else ''))
    return (rstr, rint)

#===============================================================================
def roll_list(dice, sides):
    return [random.randint(1, sides) for i in xrange(dice)]
