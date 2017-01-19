from collections import namedtuple
from itertools import *
from functools import *
import re
import random
import math
import os.path
import time
import json
import datetime

from untwisted.magic import sign

import util
import message
import modal
import channel

link, install, uninstall = util.LinkSet().triple()

DEF_FILE = 'state/roll_def.json'
DEF_MAX_TOTAL = 100000
DEF_MAX_PER_CHAN = 1000
DEF_MAX_PER_USER = 100
DEF_MAX_NAME_LEN = 32
DEF_DECAY_S = 30 * 24 * 60 * 60

MAX_ROLL = 99, 9999, 99999999

#===============================================================================
@link('HELP*', ('BRIDGE', 'HELP*'))
def h_help(bot, reply, args):
    reply('roll MdN[+K|-K]', 'Simulates the rolling of dice.')

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

#-------------------------------------------------------------------------------
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
            reply(from_name=lambda name: '* %s %s' % (name, msg), prefix=False)
        else:
            reply(msg)
    except UserError as e:
        reply('Error: %s' % e.message)

#-------------------------------------------------------------------------------
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

#-------------------------------------------------------------------------------
ABBREV_MAX_LEN = 50
def abbrev_middle(str):
    if len(str) <= ABBREV_MAX_LEN: return str
    left_len = (ABBREV_MAX_LEN - 3)/2
    right_len = (ABBREV_MAX_LEN - 3) - left_len
    return str[:left_len] + '...' + str[-right_len:]

#-------------------------------------------------------------------------------
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

#-------------------------------------------------------------------------------
def roll_list(dice, sides):
    return [random.randint(1, sides) for i in xrange(dice)]

#===============================================================================
# Evaluator of abstract syntax trees produced by the !roll argument parser.

class OutputRecord(object):
    __slots__ = 'written'
    def __init__(self, written=0):
        self.written = written

def eval_string(*args, **kwds):
    return ''.join(eval_string_parts(*args, **kwds))

def eval_string_parts(string, max_len=None):
    output = OutputRecord()
    for s in e_string(string, output):
        output.written += len(s)
        if max_len is None or output.written < max_len:
            yield s
        else:
            yield s if output.written == max_len else s[:max_len-output.written]
            break

def e_string(string, output):
    for part in string.parts:
        for s in e_part(part, output): yield s

def e_part(part, output):
    if   isinstance(part, (Text, Escape)): return e_text(part, output)
    elif isinstance(part, Roll):           return e_roll(part, output)
    elif isinstance(part, ExRoll):         return e_ex_roll(part, output)
    elif isinstance(part, Name):           return e_name(part, output)
    elif isinstance(part, Branch):         return e_branch(part, output)
    else:                                  assert False

def e_text(text, output):
    yield text.text

def e_roll(roll, output):
    raise NotImplementedError

def e_ex_roll(ex_roll, output):
    raise NotImplementedError

def e_branch(branch, output):
    raise NotImplementedError

def e_name(name, output):
    raise NotImplementedError

#===============================================================================
# Parser for the argument of !roll, producing an abstract syntax tree.

String = namedtuple('String', ('parts',                  'source'))
Text   = namedtuple('Text',   ('text',                   'source'))
Escape = namedtuple('Escape', ('text',                   'source'))
Roll   = namedtuple('Roll',   ('dice', 'sides', 'add',   'source'))
ExRoll = namedtuple('ExRoll', ('type', 'number', 'roll', 'source'))
Name   = namedtuple('Name',   ('name',                   'source'))
Branch = namedtuple('Branch', ('choices',                'source'))
Choice = namedtuple('Choice', ('weight', 'string',       'source'))

def parse_string(input):
    string, remain = p_string(ParseInput(input))
    assert not remain
    return string

def p_string(input, choice=False):
    if choice:
        text_re = re.compile(r'([^,}][^bBwWdD\d{,}\\]*)?')
        part_ps = p_escape, p_ex_roll, p_roll, p_name, p_branch
    else:
        text_re = re.compile(r'.[^bBwWdD\d{]*')
        part_ps = p_ex_roll, p_roll, p_name, p_branch

    start = input
    parts = []
    while input:
        for p_part in part_ps:
            try:
                part, input = p_part(input)
                parts.append(part)
                break
            except ParseFail:
                continue
        else:
            text_start, (match, input) = input, p_match(text_re, input)
            if not match.group():
                break
            if parts and isinstance(parts[-1], Text):
                parts[-1] = Text(
                    text   = parts[-1].text + match.group(),
                    source = parts[-1].source + (input-text_start))
            else:
                parts.append(Text(text=match.group(), source=input-text_start))

    if parts and isinstance(parts[0], Text):
        parts[0] = parts[0]._replace(text=parts[0].text.lstrip())
        if not parts[0].text: parts.pop(0)
    if parts and isinstance(parts[-1], Text):
        parts[-1] = parts[-1]._replace(text=parts[-1].text.rstrip())
        if not parts[-1].text: parts.pop(-1)

    return String(parts=parts, source=input-start), input

def p_choice_string(input):
    return p_string(input, choice=True)

def p_ex_roll(input):
    match, roll, _, end_input = p_seq(
        (p_match, r'(?P<t>[bBwW])(?P<n>\d*)\('), p_roll, (p_token, ')'), input)
    return ExRoll(
        type   = match.group('t').lower(),
        number = int(match.group('n')) if match.group('n') else 1,
        roll   = roll,
        source = end_input - input), end_input

def p_roll(input):
    match, end_input = p_match(r'(?P<d>\d*)[dD](?P<s>\d+)(?P<a>[+-]\d+)?', input)
    return Roll(
        dice   = int(match.group('d')) if match.group('d') else 1,
        sides  = int(match.group('s')),
        add    = int(match.group('a')) if match.group('a') else 0,
        source = end_input - input), end_input

def p_name(input):
    match, end_input = p_match(r'\{\{(?P<n>[a-zA-Z_-][a-zA-Z0-9_-]*)\}\}', input)
    return Name(name=match.group('n'), source=end_input-input), end_input

def p_branch(start_input):
    choices = []
    _, input = p_token('{', start_input)
    while True:
        choice, input = p_choice(input)
        choices.append(choice)
        try:
            _, input = p_token(',', input)
        except ParseFail:
            break
    _, input = p_token('}', input)
    return Branch(choices=choices, source=input-start_input), input

def p_choice(start_input):
    match, string, input = p_seq(
        (p_match, r'(\s*(?P<w>\d*\.\d+)\s*:)?'), p_choice_string, start_input)
    return Choice(
        weight = float(match.group('w')) if match.group('w') else 1.0,
        string = string,
        source = input - start_input), input

def p_escape(input):
    match, end_input = p_match(r'\\(?P<c>.)', input)
    return Escape(text=match.group('c'), source=end_input-input), end_input

#-------------------------------------------------------------------------------
# General parsing utilities.

class ParseFail(Exception):
    pass

class ParseInput(object):
    __slots__ = 'string', 'position'
    def __init__(self, string, position=0):
        self.string, self.position = string, position
    def move(self, new_position):
        return ParseInput(self.string, new_position)
    def __nonzero__(self):
        return self.position < len(self.string)
    def __sub__(self, other):
        if isinstance(other, ParseInput):
            assert self.string is other.string
            return ParseSource(self.string, other.position, self.position)
        else:
            return NotImplemented
    def __repr__(self):
        return 'Input[%d:%d]' % (self.position, len(self.string))

class ParseSource(object):
    __slots__ = 'string', 'start', 'end'
    def __init__(self, string, start, end):
        self.string, self.start, self.end = string, start, end
    def __str__(self):
        return self.string[self.start:self.end]
    def __add__(self, other):
        if isinstance(other, ParseSource):
            assert self.string is other.string and self.end == other.start
            return ParseSource(self.string, self.start, other.end)
        else:
            return NotImplemented
    def __repr__(self):
        return 'Source[%d:%d]' % (self.start, self.end)

def p_match(regex, input, flags=None):
    if isinstance(regex, str):
        regex = re.compile(regex) if flags is None else re.compile(regex, flags)
    else:
        assert flags is None
    match = regex.match(input.string, input.position)
    if match is not None:
        return match, input.move(match.end())
    else:
        raise ParseFail

def p_token(token, input):
    return p_match(re.escape(token), input)

def p_seq(*args):
    def p_seq_iter(items, input):
        for item in items:
            if isinstance(item, tuple):
                item = partial(item[0], *item[1:])
            value, input = item(input)
            yield value
        yield input
    return tuple(p_seq_iter(args[:-1], args[-1]))

#===============================================================================
# Maintenance of global definitions.

def load_defs():
    if not os.path.exists(DEF_FILE):
        return {}
    with open(DEF_FILE, 'r') as file:
        jdict = util.recursive_encode(json.load(file), 'utf8')
        return {c: GlobalDefs(jdict=d) for (c,d) in jdict.iteritems()}

def save_defs():
    prune_defs()
    jstring = json.dumps({
        c: d.save_jdict() for (c,d) in global_defs.iteritems()})
    with open(DEF_FILE, 'w') as file:
        file.write(jstring)

def prune_defs():
    now, to_remove = int(time.time()), []
    for name, defs in global_defs.iteritems():
        if name in channel.track_channels:
            defs.decay_start = None
        elif defs.decay_start is None:
            defs.decay_start = now
        elif defs.decay_start < now - DEF_DECAY_S:
            to_remove.append(name)
    for name in to_remove:
        del global_defs[name]

class GlobalDefs(dict):
    __slots__ = 'decay_start'
    def __init__(self, decay_start=None, jdict=None):
        super(GlobalDefs, self).__init__()
        if jdict is None:
            self.decay_start = decay_start
        else:
            for n, d in jdict['names'].iteritems():
                self[n] = GlobalDef(name=n, jdict=d)
            self.decay_start = jdict.get('decay_start')
    def save_jdict(self):
        jdict = {
            'names': {n: d.save_jdict() for (n, d) in self.iteritems()}}
        if self.decay_start is not None:
            jdict['decay_start'] = self.decay_start
        return jdict
    def touch(self):
        if self.decay_start is not None:
            self.decay_start = time.time()

class Def(object):
    __slots__ = 'body'
    def __init__(self, body=None, jdict=None):
        if jdict is None:
            self.body = body
        else:
            self.body = jdict['body']
    def save_jdict(self):
        return {'body': self.body}

class GlobalDef(Def):
    __slots__ = 'name', 'id', 'modes', 'time'
    def __init__(
        self, name='', id=None, modes=None, time=None, jdict=None, *a, **k
    ):
        super(GlobalDef, self).__init__(*a, jdict=jdict, **k)
        self.name = name
        if jdict is None:
            self.id, self.modes, self.time = id, modes, time
        else:
            self.id = util.ID(*jdict['id']) if 'id' in jdict else None
            self.modes = jdict.get('modes')
            self.time = jdict.get('time')
    def save_jdict(self):
        jdict = super(GlobalDef, self).save_jdict()
        if self.id is not None:
            jdict['id'] = list(self.id)
        if self.modes is not None:
            jdict['modes'] = self.modes
        if self.time is not None:
            jdict['time'] = self.time
        return jdict

global_defs = load_defs()

#-------------------------------------------------------------------------------
@link(('HELP', 'roll-def+'), ('HELP', 'rd+'))
def h_help_roll_def_p(bot, reply, args):
    reply('!roll-def+\2 or \2!rd+ NAME [=] BODY...',
    'Associate NAME with BODY so that any occurrences of \2{{NAME}}\2 in'
    ' subsequent \2!roll\2 commands will be replaced with BODY, which may'
    ' itself contain !roll syntax to be evaluated as normal. NAME is case'
    '-sensitive, must consist only of letters, digits, \2-\2 and \2_\2, not'
    ' start with a digit, and be no longer than %d characters. Example:'
    ' "!rd+ bev {tea,coffee}", "!r I will drink {{bev}}.". See also:'
    ' \2!help roll\2, \2!help rd-\2, \2!help rd?.\2' % DEF_MAX_NAME_LEN)

@link('!roll-def+', '!rd+')
def h_roll_def_p(bot, id, target, args, full_msg):
    name, body = re.match(r'([^\s=]*)\s*=?\s*(.*)', args).groups()
    body = body.strip()
    if len(name) > DEF_MAX_NAME_LEN or not re.match(r'(?!\d)[\w-]+$', name):
        return message.reply(bot, id, target, 'Error: you must specify a name'
        ' consisting of letters, digits, \2-\2 and \2_\2, not starting with a'
        ' digit and no longer than %d characters. See \2!help roll-def+\2 for'
        ' correct usage.' % DEF_MAX_NAME_LEN)

    if sum(len(d) for d in global_defs.itervalues()) >= DEF_MAX_TOTAL:
        return message.reply(bot, id, target, 'Error: there are too many defin'
        'itions stored. Please notify the bot administrator of this message.')

    now = int(time.time())
    chan = (target or ('%s!%s@%s' % id)).lower()
    defs = global_defs.get(chan) or GlobalDefs()

    if target is None:
        u = re.compile('@%s$' % re.escape(id.host) if id.user.startswith('~')
            else '!(~.*|%s)@%s$' % (re.escape(id.user), re.escape(id.host)))
        udefs = sum(len(d) for (c,d) in global_defs.iteritems() if u.search(c))
    else:
        if len(defs) > DEF_MAX_PER_CHAN: return message.reply(bot, id, target,
            'Error: this channel has too many definitions - no more than %d are'
            ' permitted. See \2!help roll-def-\2 to delete existing definitions.'
            % DEF_MAX_PER_CHAN)
        is_op = channel.has_op_in(bot, id.nick, chan, 'h')
        udefs = None if is_op else \
                sum(1 for d in defs.itervalues() if util.same_user(d.id, id))

    if udefs is not None and udefs >= DEF_MAX_PER_USER:
        return message.reply(bot, id, target, 'Error: you have made too many'
        ' definitions here - no more than %d are permitted. See \2!help'
        ' roll-def-\2 to delete existing definitions.' % DEF_MAX_PER_USER)

    if target is not None and not is_op and name in defs \
    and defs[name].id and not util.same_user(defs[name].id, id):
        return message.reply(bot, id, target, 'Error: this name is already'
        ' defined by %s!%s@%s; only the same user or an operator may change it.'
        % defs[name].id)

    modes = channel.umode_channels[chan].get(id.nick.lower(), '')
    defs[name] = GlobalDef(name=name, id=id, modes=modes, time=now, body=body)
    defs.touch()
    global_defs[chan] = defs
    save_defs()

    message.reply(bot, id, target, 'Defined.')

#-------------------------------------------------------------------------------
@link(('HELP', 'roll-def-'), ('HELP', 'rd-'))
def h_help_roll_def_m(bot, reply, args):
    reply('!roll-def-\2 or \2!rd- NAME1 [NAME2 ...]',
    'Delete the definitions made using \2!rd+\2 of each given NAME. If the user'
    ' is not a channel operator, only definitions made by the same user will be'
    ' deleted. Each NAME may contain wildcard characters \2?\2 and \2*\2, may'
    ' consist of a hostmask, or may may be preceded by \2!\2 to prevent its'
    ' deletion, as in \2!rd?\2. All names are case-sensitive. See also: \2!help'
    ' rd+\2, \2!help rd?\2.')

@link('!roll-def-', '!rd-')
def h_roll_def_m(bot, id, target, args, full_msg):
    args = args.split()
    if all(a.startswith('!') for a in args):
        return message.reply(bot, id, target,
        'Error: you must specify at least one name to delete. See \2!help'
        ' rd-\2 for correct usage.')
    chan = (target or ('%s!%s@%s' % id)).lower()

    defs = list(def_search(chan, args))
    if target is None or channel.has_op_in(bot, id.nick, chan, 'h'):
        ddefs, udefs = defs, []
    else:
        ddefs, udefs = [], []
        for defn in defs:
            (ddefs if util.same_user(id, defn.id) else udefs).append(defn)

    if chan in global_defs:
        for defn in ddefs:
            del global_defs[chan][defn.name]
        global_defs[chan].touch()
        if not global_defs[chan]:
            del global_defs[chan]
        save_defs()

    udefs_str = ', '.join(d.name for d in udefs)
    if len(udefs_str) > 300: udefs_str = udefs_str[:300] + '(...)'
    message.reply(bot, id, target, '%s definition%s deleted.%s' % (
        len(ddefs), '' if len(ddefs) == 1 else 's',
        '' if not udefs else (' %d matching definition%s *not* deleted: %s.'
        % (len(udefs), '' if len(udefs) == 1 else 's', udefs_str))))

#-------------------------------------------------------------------------------
@link(('HELP', 'roll-def?'), ('HELP', 'rd?'))
def h_help_roll_def_q(bot, reply, args):
    reply('!roll-def?\2 or \2!rd? [#CHANNEL] [NAME1 [NAME2 ...]]',
    'Show the definitions made using \2!rd+\2 of each given NAME. Names may'
    ' contain the wildcard characters \2?\2 and \2*\2, meaning exactly one and'
    ' zero or more characters, respectively. Names of the form'
    ' \2NICK!USER@HOST\2 match all definitions made by the given user. Names'
    ' starting with \2!\2 are excluded from the result rather than included. If'
    ' given, #CHANNEL is searched rather than the current channel. See also:'
    ' \2!help rd+\2, \2!help rd-\2.')

@link('!roll-def?', '!rd?')
def h_roll_def_q(bot, id, target, args, full_msg):
    args = args.split()
    if args and args[0].startswith('#'):
        chan = args.pop(0)
        chan_case = channel.capitalisation.get(chan, chan)
        chan = chan.lower()
        nick = id.nick.lower()
        if not any(nick == n.lower() for n in channel.track_channels[chan]):
            return message.reply(bot, id, target,
                'Error: both you and this bot must be present in %s to search'
                ' its definitions.' % chan_case)
        chan_external = True
    elif target is not None:
        chan = target.lower()
        chan_case = channel.capitalisation.get(chan, target)
        chan_external = False
    else:
        chan_case = '%s!%s@%s' % id
        chan = chan_case.lower()
        if chan in global_defs:
            global_defs[chan].touch()
        chan_external = False
   
    defs = sorted(def_search(chan, args), key=lambda d: d.time)
    s = 's' if len(defs) != 1 else ''
    noun = 'definition%s' % s if not chan_external else \
           'definition%s in %s' % (s, chan_case) if chan.startswith('#') else \
           'private definition%s' % s
    defs_str = '%d matching %s' % (len(defs), noun)

    if len(defs) == 0:
        message.reply(bot, id, target, '%s.' % defs_str, prefix=False)
    elif len(defs) == 1:
        defn = defs[0]
        if defn.time is not None:
            dt_set = datetime.datetime.utcfromtimestamp(defn.time)
            delta = datetime.datetime.utcnow() - dt_set
            d_mins, d_secs = divmod(delta.seconds, 60)
            d_hours, d_mins = divmod(d_mins, 60)
            time_str = ' on %s UTC (%sd, %02d:%02d:%02d ago)' % (
                dt_set.strftime('%d %b %Y, %H:%M'),
                delta.days, d_hours, d_mins, d_secs)
        else:
            time_str = ''
        message.reply(bot, id, target,
            '%s, set%s%s:' % (
                defs_str,
                (' by %s!%s@%s' % defn.id) if chan.startswith('#') else '',
                time_str),
            prefix=False)
        message.reply(bot, id, target,
            '    %s = %s' % (defn.name, defn.body), prefix=False)
    elif len(defs) <= 4:
        message.reply(bot, id, target, '%s:' % defs_str, prefix=False)
        for row in util.join_rows(*((d.name, d.body) for d in defs), sep=' = '):
            message.reply(bot, id, target, '    %s' % row, prefix=False)
    else:
        names = ', '.join(d.name for d in defs)
        if len(names) > 300: names = names[:300] + '(...)'
        message.reply(bot, id, target,
            '%s: %s. Use \2!rd?%s NAME\2 to view the details of a definition.'
            % (defs_str, names, (' %s' % chan_case)
            if chan_external and not (target and target.lower() == chan) else ''),
            prefix=False)

# An iterator (in no particular order) over the definitions matched by `queries'
# as per !rd? and !rd-.
def def_search(chan, queries):
    pos, neg = [], []
    for query in queries:
        if query.startswith('!'):
            neg.append(query[1:])
        else:
            pos.append(query)
    if not pos:
        pos.append('*')
    return (d for d in global_defs.get(chan, {}).itervalues()
            if any(def_match(q, d) for q in pos)
            and not any(def_match(q, d) for q in neg))

# True iff `query' positively matches `defn' as per !rd? and !rd-.
def def_match(query, defn):
    if '!' in query or '@' in query:
        id_str = ('%s!%s@%s' % defn.id) if defn.id is not None else '*!*@*'
        return re.match(util.wc_to_re(query), id_str, flags=re.I) is not None
    else:
        return re.match(util.wc_to_re(query), defn.name) is not None
