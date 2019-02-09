from collections import namedtuple
from UserDict import DictMixin
from itertools import *
from functools import *
from cStringIO import StringIO
from contextlib import contextmanager
from numbers import Integral
import re
import random
import math
import os
import os.path
import time
import json
import datetime
import string
import sys

from untwisted.magic import sign

import util
import message
import modal
import channel

link, install, uninstall = util.LinkSet().triple()

DEF_FILE = 'state/roll_def.json'
DEF_BACKUP_NAME = 'state/roll_def.json.d/roll_def.%d.json'
DEF_BACKUPS = 9

DEF_MAX_TOTAL = 100000
DEF_MAX_PER_CHAN = 1000
DEF_MAX_PER_USER = 100
DEF_MAX_NAME_LEN = 32
DEF_DECAY_S = 30 * 24 * 60 * 60
RESERVED_NAMES = 'me', 'nick', 'dF'

MAX_ROLL             = 999, 999999999, 999999999
MAX_DICE_DEF_LEN     = 200
MAX_DICE_STACK_DEPTH = 100

MAX_NAMES_EXPANDED = 5000
MAX_STACK_DEPTH    = 500
MAX_MESSAGE_LENGTH = 400

#===============================================================================
@link('HELP*', ('BRIDGE', 'HELP*'))
def h_help(bot, reply, args):
    reply('roll MdN[+K|-K]',
    'Simulates the rolling of dice, and other random processes.')

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
        reply('roll ... {[WEIGHT1:]ITEM1, [WEIGHT2:]ITEM2, ...} ...',
        'For each comma-separated list of items enclosed in curly braces,'
        ' chooses one item at random and replaces the list with that item.'
        ' Items are selected with probability proportional to their WEIGHT,'
        ' which can be specified as a positive number followed by a colon'
        ' before the item, or otherwise defaults to 1. Each item may contain'
        ' dice rolls, further brace-delimited lists, or other !roll syntax.',
        'Within a brace-delimited list, any backslash character (\2\\\2)'
        ' followed by any other character will be replaced by the second character'
        ' verbatim in the output, preventing it from having any special meaning.'
        ' Any space characters not preceded by a backslash at the beginning or'
        ' end of an ITEM will be removed. For further advanced features,'
        ' see \2!help roll 3\2.')
    elif args and int(args) == 3 and not bridge:
        reply('roll ... {{NAME}} ...',
        'Where NAME corresponds to a definition set using \2roll-def+\2,'
        ' {{NAME}} is replaced with the body of the definition, which is itself'
        ' further expanded if it contains any !roll syntax. If NAME has been'
        ' altered by making some characters uppercase or lowercase, a corresponding'
        ' transformation will be applied to the result.'
        ' See also: \2!help roll-def+\2.')
    else:
        reply('roll MdN\2 or \2!roll MdN+K\2 or \2!roll MdN-K',
        'Simulates the rolling of M dice, each of which has N sides, giving'
        ' the sum of the individual results. Optionally, adds (for MdN+K) or'
        ' subtracts (for MdN-K) a value of K to or from the result. Example:'
        ' "!roll 2d6+1".' +
        (' For advanced features, see \2!help roll 2\2 and \2!help roll 3\2,'
        ' preferably in a private message. See also: \2!help missed-rolls\2.'
        if not bridge else ''))

        if 'url' in sys.modules and bot in sys.modules['url'].link.installed_modes:
            reply('url !roll ...\2 or \2!url !r ...',
            'Executes the \2!roll\2 command as usual, then executes the \2!url\2'
            ' command on its result, analysing any URLs present in it. See'
            ' \2!help url\2 for more information.')

#-------------------------------------------------------------------------------
class UserError(Exception):
    pass

@link('!roll', '!r', action=False)
@link(('ACTION', '!roll'), ('ACTION', '!r'), action=True)
def h_roll(bot, id, target, args, full_msg, action):
    def reply(rmsg):
        message.reply(bot, id, target, rmsg, prefix=False)
        bot.drive('runtime.later', sign('PROXY_MSG', bot, id, target, rmsg))
    return roll(bot, id, target, args, action, reply)

def roll(bot, id, target, args, action=False, reply=None, error_reply=None):
    reply = reply or (lambda rmsg: rmsg)
    error_reply = error_reply or reply
    def reply_(rmsg=None, from_name=None, prefix=True):
        if rmsg is None: rmsg = from_name(id.nick)
        if prefix and target is not None: rmsg = '%s: %s' % (id.nick, rmsg)
        return reply(rmsg)
    def error_reply_(rmsg=None, from_name=None, prefix=True):
        if rmsg is None: rmsg = from_name(id.nick)
        if prefix and target is not None: rmsg = '%s: %s' % (id.nick, rmsg)
        return error_reply(rmsg)
    defs = PrivateDefs(id) if target is None else global_defs.get(target.lower())
    defs = AutoDefs(defs)
    return h_roll_defs(bot, id, target, args, defs, action, reply_, error_reply_)

@link(('BRIDGE','!roll'), ('BRIDGE','!r'), action=False)
@link(('BRIDGE','ACTION','!roll'), ('BRIDGE','ACTION','!r'), action=True)
def h_simple_roll(bot, name, target, args, reply, action):
    id = util.ID(name, '*', '*')
    return h_roll_defs(bot, id, target, args, None, action, reply, reply)

def h_roll_defs(bot, id, target, args, defs, action, reply, error_reply):
    try:
        msg, rolls = eval_string(
            parse_string(args), defs=defs, user_id=id, irc=True,
            max_len            = MAX_MESSAGE_LENGTH,
            max_names_expanded = MAX_NAMES_EXPANDED,
            max_stack_depth    = MAX_STACK_DEPTH)

        if target and target.startswith('#'):
            bot.drive('DICE_ROLLS', bot, id, target, rolls, msg)

        if action:
            from_name = lambda name: '* %s %s' % (name, msg)
            return reply(from_name=from_name, prefix=False)
        else:
            return reply(msg)
    except UserError as e:
        return error_reply('Error: %s' % e.message)
    except Exception as e:
        error_reply('Error: %r' % e)
        raise

#===============================================================================
# Evaluation of abstract syntax trees produced by the !roll argument parser.

class RollNameError(NameError):
    pass

class CancelExpansion(Exception):
    pass

class EvalRecord():
    __slots__ = 'names_expanded', 'stack_depth'
    def __init__(self):
        self.names_expanded = 0
        self.stack_depth = 0

EvalContext = namedtuple('EvalContext', (
    'defs', 'user_id', 'record', 'max_names_expanded', 'max_stack_depth'))

# Returns (str, [roll_spec_1, roll_spec_2, ...])
def eval_string(*args, **kwds):
    parts, rolls = eval_string_parts(*args, **kwds)
    return (''.join(parts), rolls)

# Returns (str_iterator, [roll_spec_1, roll_spec_2, ...])
def eval_string_parts(
    string, max_len=None, irc=False, defs=None, user_id=None,
    max_names_expanded=None, max_stack_depth=None
):
    context = EvalContext(
        defs=defs, user_id=user_id, record=EvalRecord(),
        max_names_expanded=max_names_expanded,
        max_stack_depth=max_stack_depth)

    rolls = []
    parts = list(string.parts)
    for i, part in zip(count(), string.parts):
        if isinstance(part, Expr):
            try:
                text, spec = eval_expr_spec(part, context, irc=irc)
                parts[i] = Text(text=text, source=part.source)
                if spec is not None: rolls.append(spec)
            except CancelExpansion:
                pass
    string = string._replace(parts=parts)

    def eval_string_parts_iter():
        written = 0
        for s in e_string(string, context):
            written += len(s)
            if max_len is None or written <= max_len:
                yield s
            else:
                yield s[:max_len-written] + '(...)'
                break

    return (eval_string_parts_iter(), rolls)

#-------------------------------------------------------------------------------
# Evaluation of AST nodes below the top level or after preprocessing.
def e_string(string, context):
    return chain(*(
        e_text(part, context)       if isinstance(part, (Text, Escape)) else
        e_expr(part, context)       if isinstance(part, Expr)           else
        e_name_app(part, context)   if isinstance(part, NameApp)        else
        e_string_app(part, context) if isinstance(part, StringApp)      else
        e_branch(part, context)     if isinstance(part, Branch)         else
    None for part in string.parts))

def e_text(text, context):
    yield text.text

def e_expr(expr, context):
    try:
        yield str(eval_expr_int(expr, context))
    except CancelExpansion:
        yield str(expr.source)

def e_branch(branch, context):
    weight_sum = 0.0
    weight_sums = []
    for choice in branch.choices:
        if choice.weight <= 0: raise UserError(
            'The weight in "%s" is too small.' % abbrev_right(str(branch.source)))
        weight_sum += choice.weight
        weight_sums.append(weight_sum)

    if math.isinf(weight_sum): raise UserError(
        'The weights in "%s" are too large.' % abbrev_middle(str(branch.source)))
    if math.isnan(weight_sum): raise UserError(
        'The weights in "%s" are invalid.' % abbrev_middle(str(branch.source)))

    chosen_number = random.uniform(0, weight_sum)
    for partial_weight_sum, choice in izip(weight_sums, branch.choices):
        if chosen_number < partial_weight_sum:
            chosen = choice
            break
    else:
        chosen = branch.choices[-1]

    return e_string(chosen.string, context)

def e_name_app(name_app, context):
    try:
        parts = e_name_(name_app.name.name, name_app.name.namespace,
                        name_app.name, context)
        return e_func_app(name_app.suffixes, parts, name_app, context)
    except RollNameError:
        return (str(name_app.source),)

def e_string_app(string_app, context):
    parts = e_string(string_app.string, context)
    return e_func_app(string_app.suffixes, parts, string_app, context)

def e_func_app(func_names, value_parts, node, context):
    for func_name in func_names:
        func = rd_functions.get(func_name.name)
        if func is None: return (str(node.source),)
        value_parts = func(context, value_parts)
    return value_parts

def e_name_(name, namespace, ast_node, context):
    if namespace is not None:
        if context.user_id is None:
            raise RollNameError(str(ast_node.source))
        chan_lower = namespace.lower()
        if context.user_id.nick.lower() not in \
        map(str.lower, channel.track_channels[chan_lower]):
            raise UserError('To use "%s", you and this bot must both be in %s.'
            % (abbrev_middle(str(ast_node.source)), abbrev_right(namespace)))
        context = context._replace(defs=AutoDefs(global_defs.get(chan_lower)))
    if context.defs is None or name not in context.defs:
        raise RollNameError(name)
    def e_name_gen():
        with expanding_name(context):
            defn = context.defs[name]
            for s in defn.postprocess(e_string(defn.body_ast, context), context):
                yield s
    return e_name_gen()

@contextmanager
def expanding_name(context):
    if context.max_stack_depth is not None:
        context.record.stack_depth += 1
        if context.record.stack_depth >= context.max_stack_depth:
            raise UserError('In evaluating this result, the maximum recursion'
            ' depth of %d would be exceeded.' % context.max_stack_depth)

    if context.max_names_expanded is not None:
        context.record.names_expanded += 1
        if context.record.names_expanded >= context.max_names_expanded:
            raise UserError('In evaluating this result, more than the maximum'
            ' of %d definitions would be expanded.' % context.max_names_expanded)

    yield context

    if context.max_stack_depth is not None:
        context.record.stack_depth -= 1

#-------------------------------------------------------------------------------
# Evaluation of dice rolls from abstract syntax tree nodes:

# Returns an integer.
def eval_expr_int(expr, context=None):
    def eval_parts(parts):
        total = 0
        for part in parts:
            if isinstance(part, tuple):
                sign, p_parts = part[:2]
                total += sign * eval_parts(p_parts)
            elif isinstance(part, Integral):
                total += part
            else:
                raise TypeError(part)
        return total
    return eval_parts(eval_expr_iter(expr, context))

# Returns (str, (((dice, drop_l, drop_h), sides, add), int) or None)
def eval_expr_spec(expr, context=None, irc=False):
    s = type('State', (object,), {})()
    s.r_int, s.n_terms, r_str = 0, 0, StringIO()
    s.head_paren, s.tail_paren, s.drop_paren = False, False, False

    def eval_parts(parts, sign=1, start=False, cnst=False, drop=False):
        dice, sides, add, drop_l, drop_h = 0, 0, 0, 0, 0
        for part in parts:
            if cnst and not (s.head_paren or s.tail_paren):
                r_str.write('(')
                s.head_paren, s.tail_paren = start, not start

            o_sign = sign*part if isinstance(part, Integral) else sign*part[0]
            if isinstance(part, Integral) \
            or isinstance(part[3], TermKeep) and o_sign < 0:
                if s.tail_paren and not cnst: r_str.write(')')
                if drop and not s.drop_paren:
                    r_str.write('[')
                    s.drop_paren = True
                if (o_sign >= 0 or s.head_paren) and not start: r_str.write('+')
                if s.head_paren and not cnst: r_str.write(')')
                if o_sign < 0: r_str.write('-')
                if not cnst: s.head_paren, s.tail_paren = False, False

            if isinstance(part, Integral):
                num = -sign*part if o_sign < 0 else sign*part
                r_str.write('(%d)' % num if num < 0 else str(num))
                add += sign*part
                s.r_int += sign*part
                s.n_terms += 1
            else:
                p_sign, p_parts, p_spec, p_term = part
                if isinstance(p_term, TermKeep) and o_sign < 0:
                    r_str.write('(')
                    s.r_int *= o_sign
                    pp_spec = eval_parts(p_parts, start=True)
                    s.r_int *= o_sign
                    r_str.write(')')
                else:
                    p_cnst = isinstance(p_term, TermCnst)
                    if p_spec is not None and p_spec[-2:] != (0, 0):
                        eval_parts([sum(p_parts)], o_sign, start, p_cnst, True)
                        r_str.write(']')
                        s.drop_paren = False
                    else:
                        pp_spec = eval_parts(p_parts, o_sign, start, p_cnst)
                if p_spec is None: p_spec = pp_spec
                p_dice, p_sides, p_add, p_drop_l, p_drop_h = p_spec
                sides = p_sides if sides == 0 or sides == p_sides else \
                        sides if p_sides == 0 else None
                dice, add = dice+p_dice, add+p_add
                if p_drop_l != 0 or p_drop_h != 0:
                    if drop_l == drop_h == 0: drop_l, drop_h = p_drop_l, p_drop_h
                    else: sides, drop_l, drop_h = None, None, None

            start = False
        return dice, sides, add, drop_l, drop_h

    spec = eval_parts(eval_expr_iter(expr, context), start=True)
    if s.head_paren or s.tail_paren: r_str.write(')')
    dice, sides, add, drop_l, drop_h = spec
    r_spec = None if sides is None else \
             (((dice, drop_l, drop_h), sides, add), s.r_int)
    r_str = ('%(b)s%(int)d%(b)s=%(str)s' if s.n_terms > 1 else
             '%(b)s%(int)d%(b)s') \
             % {'b':'\2' if irc else '', 'int':s.r_int, 'str':r_str.getvalue()}
    return (r_str, r_spec)

# Yields one or more terms of the form
#   term = (sign, [part1, part2, ...], spec or None, ast_node or None)
# representing sign * (part1 + part2 + ...), where
#   sign = 1 or -1
#   part = term or int
#   spec = (dice, sides, add, drop_low, drop_high)
def eval_expr_iter(expr, context=None, reduce=False):
    top_expr = expr
    while expr is not None:
        term = expr.term
        sign = 1 if expr.op == '+' else -1

        if isinstance(term, (TermDice, TermDiceC, TermDiceD)):
            if term.dice > MAX_ROLL[0]: raise UserError(
                'The number of dice in "%s" is too large: the maximum is %d.'
                % (abbrev_middle(str(term.source)), MAX_ROLL[0]))

        if isinstance(term, TermDice):
            if term.sides == 0: raise UserError(
                'The number of sides in "%s" is invalid: it must be positive.'
                % abbrev_middle(str(term.source)))
            if term.sides > MAX_ROLL[1]: raise UserError('The number of'
                ' sides in "%s" is too large: the maximum is %d.'
                % (abbrev_middle(str(term.source)), MAX_ROLL[1]))
            rolls = [random.randint(1, term.sides) for i in xrange(term.dice)]
            yield (sign, rolls, (term.dice, term.sides, 0, 0, 0), term)

        elif isinstance(term, TermDiceC):
            if term.num > MAX_ROLL[1]: raise UserError(
                'The constant %s in "%s" is too large: the maximum is %d.'
                % (abbrev_right(str(term.num)),
                   abbrev_middle(str(term.source)), MAX_ROLL[1]))
            rolls = [term.num] * term.dice
            yield (sign, rolls, (0, 0, term.dice*term.num, 0, 0), term)

        elif isinstance(term, TermDiceD):
            try:
                rolls = roll_dice_def(
                    term.dice, 'd'+term.name, term, context, reduce)
            except RollNameError:
                # In this special case where the user might have not intended
                # a dice roll, ignore the error instead of reporting it:
                if not reduce and expr is top_expr and expr.expr is None \
                and term.source.start > 0 and str(term.source)[:1].isalpha():
                    raise CancelExpansion
                may = context is not None and len(term.name) < DEF_MAX_NAME_LEN
                raise UserError('The die type "%s" in "%s" is not defined.%s'
                    % (abbrev_right(term.name),
                       abbrev_middle(str(top_expr.source)),
                       (' You may define it here with \2!roll-def+ d%s ='
                        ' {SIDE1,SIDE2,...}\2. See also: \2!help roll-def+\2.'
                        % term.name) if may else ''))
            if any(isinstance(roll, Integral) for roll in rolls):
                yield (sign, rolls, (term.dice, term.name, 0, 0, 0), term)
            else:
                yield (sign, rolls, None, term)
 
        elif isinstance(term, TermKeep):
            parts, rolls = [], []
            for part in eval_expr_iter(term.expr, context, reduce=True):
                p_sign, p_parts, p_spec, p_term = part
                if isinstance(p_term, TermKeep): raise UserError(
                    'The occurrence of "%s" within "%s" is invalid: one best-of'
                    ' or worst-of roll may not occur inside another.'
                    % (abbrev_middle(str(p_term.source)),
                       abbrev_middle(str(term.source))))
                if isinstance(p_term, (TermDice, TermDiceC, TermDiceD)):
                    if isinstance(p_term, TermDiceC) and p_parts:
                        p_spec = p_spec[:1] + (None,) + p_spec[2:]
                    rolls.extend(p_sign * roll for roll in p_parts)
                parts.append((p_sign, p_parts, p_spec, p_term))

            if term.num > len(rolls): raise UserError('"%s" is invalid:'
                ' it is not possible to keep %d out of %d dice rolls.'
                % (abbrev_middle(str(term.source)), term.num, len(rolls)))
            drop_l = len(rolls) - term.num if term.bw == 'b' else 0
            drop_h = len(rolls) - term.num if term.bw == 'w' else 0
            dropped = sorted(rolls)
            del dropped[drop_l:len(rolls)-drop_h]
            parts.append((-1, dropped, (0, 0, 0, drop_l, drop_h), None))
            yield (sign, parts, None, term)

        elif isinstance(term, TermCnst):
            if term.num > MAX_ROLL[2]: raise UserError(
                'The constant %s in "%s" is too large: the maximum is %d.'
                % (abbrev_right(str(term.num)),
                   abbrev_middle(str(top_expr.source)), MAX_ROLL[2]))
            yield (sign, [term.num], (0, 0, sign * term.num, 0, 0), term)

        else:
            raise TypeError(expr.term)

        expr = expr.expr

def roll_dice_def(dice, name, term, context, reduce=False):
    if name == 'dF':
        return [random.randint(-1, 1) for i in xrange(dice)]

    if context is None or context.defs is None or name not in context.defs \
    or isinstance(context.defs[name], CaseAutoDef):
        raise RollNameError(name)

    context = context._replace(max_stack_depth=MAX_DICE_STACK_DEPTH)

    defn = context.defs[name]
    if not reduce and getattr(defn.postprocess, 'is_identity', False):
        ast = defn.body_ast
        if isinstance(ast, String) and len(ast.parts) == 1 \
        and isinstance(ast.parts[0], Expr):
            with expanding_name(context):
                return [x for i in xrange(dice)
                          for x in eval_expr_iter(ast.parts[0], context)]

    return [roll_dice_def_(name, term, context) for i in xrange(dice)]

def roll_dice_def_(name, term, context):
    o_str, o_len = StringIO(), 0
    for s in e_name_(name, None, term, context):
        o_str.write(s)
        o_len += len(s)
        if o_len > MAX_DICE_DEF_LEN: raise UserError('Expanding the custom die'
            ' definition for "%s" produced a string longer than the maximum'
            ' allowed length of %d: "%s(...)".'
            % (abbrev_middle(str(term.source)), MAX_DICE_DEF_LEN,
               o_str.getvalue()[:MAX_DICE_DEF_LEN]))

    o_str = o_str.getvalue()
    try: o_int = int(o_str)
    except ValueError: raise UserError('Expanding the custom die definition for'
        ' "%s" produced a string which was not recognised as an integer: "%s".'
        % (abbrev_middle(str(term.source)), o_str))
    return o_int

#===============================================================================
# Parser for the argument of !roll, producing an abstract syntax tree.

String = namedtuple('String', ('parts',                  'source'))
Text   = namedtuple('Text',   ('text',                   'source'))
Escape = namedtuple('Escape', ('text',                   'source'))

Expr      = namedtuple('Expr',      ('op', 'term', 'expr', 'source'))
TermDice  = namedtuple('TermDice',  ('dice', 'sides',      'source'))
TermDiceC = namedtuple('TermDiceC', ('dice', 'num',        'source')) # Constant
TermDiceD = namedtuple('TermDiceD', ('dice', 'name',       'source')) # Defined
TermKeep  = namedtuple('TermKeep',  ('bw', 'num', 'expr',  'source'))
TermCnst  = namedtuple('TermCnst',  ('num',                'source'))

Name      = namedtuple('Name',      ('namespace', 'name',  'source'))
NameApp   = namedtuple('NameApp',   ('name', 'suffixes',   'source'))
StringApp = namedtuple('StringApp', ('string', 'suffixes', 'source'))
Branch    = namedtuple('Branch',    ('choices',            'source'))
Choice    = namedtuple('Choice',    ('weight', 'string',   'source'))

def parse_string(input):
    string, remain = p_string(ParseInput(input))
    return string

def p_string(input, group=False):
    if group:
        text_re = re.compile(
            r'[^,}\s]((?!\b[bBwWdD])[^\d{,}\\\s+-])*|\s+(?=[^,}\s])|')
        part_ps = p_escape, p_expr, p_group, (p_text, text_re)
    else:
        text_re = re.compile(r'.((?!\b[bBwWdD])[^\d{+-])*|')
        part_ps = p_expr, p_group, (p_text, text_re)

    start = input
    parts = []
    while input:
        part, input = p_any(*part_ps + (input,))
        if isinstance(part, Text):
            if not part.text:
                break
            if parts and isinstance(parts[-1], Text):
                parts[-1] = Text(
                    text   = parts[-1].text + part.text,
                    source = parts[-1].source + part.source)
                continue
        parts.append(part)

    return String(parts=parts, source=input-start), input

def p_group(input):
    return p_any(p_name_app, p_string_app, p_branch, input)

def p_text(text_re, start):
    match, input = p_match(text_re, start)
    return Text(text=match.group(), source=input-start), input

def p_choice_string(input):
    return p_string(input, group=True)

def p_expr(start, top=True, head=True):
    match, input = p_match(r'((?P<op>[+-])' + (')?' if head else '\s*)'), start)
    op = match.group('op') or '+'
    term, input = p_any(p_term_dice, p_term_keep, p_term_cnst, input)
    try:
        tail, input = p_expr(p_match(r'\s*', input)[1], top=False, head=False)
    except ParseFail:
        tail = None
    expr = Expr(op=op, term=term, expr=tail, source=input-start)

    any_dice = any(traverse_ast(expr, TermDice, TermDiceC, TermDiceD))
    return (expr, input) if not top or any_dice else \
           (Text(text=str(expr.source), source=expr.source), input)

def p_term_dice(start):
    match, input = p_match(
        r'\b(?P<dice>\d*)(?P<dc>[dcDC])(?P<sides>\d+|[A-Z][A-Za-z0-9]*)',
        start)
    dice, dc, sides = match.group('dice', 'dc', 'sides')
    dice = int(dice) if dice else 1
    if dc.isupper() and not match.group('dice'): raise ParseFail
    if sides[0].isdigit():
        return (TermDiceC(dice, int(sides), input-start) if dc in 'cC' else
                TermDice( dice, int(sides), input-start), input)
    else:
        if dc not in 'dD': raise ParseFail
        return TermDiceD(dice, sides, input-start), input

def p_term_keep(start):
    match, input = p_match(r'\b(?P<bw>[bBwW])(?P<num>\d*)\(\s*', start)
    expr, input = p_expr(input, top=False)
    _, input = p_match(r'\s*\)', input)
    bw, num = match.group('bw', 'num')
    num = int(num) if num else 1
    return TermKeep(bw=bw, num=int(num), expr=expr, source=input-start), input

def p_term_cnst(start):
    match, input = p_match(r'\b\d+', start)
    return TermCnst(num=int(match.group()), source=input-start), input

def p_name(start_input):
    chan_match, input = p_match(r'((?P<ch>#((?!}}|/.*!)[^\s,])*)/)?', start_input)
    name_match, input = p_match(r'[^{},:\\\s!]*', input)
    return Name(namespace=chan_match.group('ch'), name=name_match.group(),
                source=input-start_input), input

def p_name_app(start):
    _, input = p_token('{{', start)
    name, input = p_name(input)
    suffixes = []
    while True:
        try: _, input = p_token('!', input)
        except ParseFail: break
        suffix, input = p_name(input)
        suffixes.append(suffix)
    _, input = p_token('}}', input)
    return NameApp(name=name, suffixes=suffixes, source=input-start), input

def p_string_app(start):
    _, input = p_match('{\s*', start)

    (group, input), group_start = p_group(input), input
    string = String(parts=[group], source=input-group_start)

    suffixes = []
    while True:
        try: _, input = p_match('\s*!\s*', input)
        except: break
        suffix, input = p_name(input)
        suffixes.append(suffix)
    if not suffixes: raise ParseFail

    _, input = p_match('\s*}', input)
    return StringApp(string=string, suffixes=suffixes, source=input-start), input

def p_branch(start_input):
    choices = []
    _, input = p_match(r'\{\s*', start_input)
    while True:
        choice, input = p_choice(input)
        choices.append(choice)
        try: _, input = p_match(r'\s*,\s*', input)
        except ParseFail: break
    _, input = p_match(r'\s*\}', input)
    return Branch(choices=choices, source=input-start_input), input

def p_choice(start_input):
    match, string, input = p_seq(
        (p_match, r'((?P<w>\d*\.?\d+)\s*:\s*)?'), p_choice_string, start_input)
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
    def __init__(self, string=None, start=None, end=None):
        self.string = '<unknown>' if string is None else string
        self.start = 0 if start is None else start
        self.end = len(self.string) if end is None else end
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

def p_any(*args):
    for parser in args[:-1]:
        if isinstance(parser, tuple):
            parser = partial(parser[0], *parser[1:])
        try:
            return parser(args[-1])
        except ParseFail:
            continue
    raise ParseFail

#===============================================================================
# Static global definitions.

rd_functions = {}

def rd_func(*names, **kwds):
    def rd_func_decorator(func):
        if kwds.get('unicode', False):
            func = unicode_rd_func(func)
        for name in names:
            assert name not in rd_functions, (name, func)
            rd_functions[name] = func
        return func
    return rd_func_decorator

def unicode_rd_func(func):
    def unicode_rd_func_(context, *args):
        def decoded(parts):
            for part in parts:
                if not part: continue
                try: yield part.decode('utf8') if type(part) is str else part
                except UnicodeDecodeError: yield part
        for part in func(context, *(decoded(arg) for arg in args)):
            yield part.encode('utf8') if type(part) is unicode else part
    return unicode_rd_func_

@rd_func('lowercase', 'lc', unicode=True)
def rd_func_lowercase(context, parts):
    return imap(string.lower, parts)

@rd_func('uppercase', 'uc', unicode=True)
def rd_func_uppercase(context, parts):
    return imap(string.upper, parts)

@rd_func('initial-capital', 'ic', unicode=True)
def rd_func_initial_capital(context, parts):
    parts = iter(parts)
    part = next(parts)
    return chain((part[0].upper() + part[1:],), parts)

@rd_func('title-case', 'tc', unicode=True)
def rd_func_title_case(context, parts):
    start_word = True
    for part in parts:
        if start_word: part = part[:1].upper() + part[1:]
        flags = re.U if type(part) is unicode else 0
        def repl(m):
            part = m.group()
            return part[0].upper() + part[1:] if m.start() else part
        yield re.sub(r"([^\W_]|')+", repl, part, 0, flags)
        start_word = re.match(r'[^\W_]', part[-1:], flags) is None

@rd_func('swap-case', 'sc', unicode=True)
def rd_func_swap_case(context, parts):
    for part in parts: yield part.swapcase()

@rd_func('alternating-case', 'ac', unicode=True)
def rd_func_alternating_case(context, parts):
    odd = [False]
    def map_char(char):
        if char.isupper() or char.islower():
            char = char.lower() if odd[0] else char.upper()
            odd[0] = not odd[0]
        return char
    for part in parts:
        yield ''.join(imap(map_char, part))

@rd_func('random-case', 'rc', unicode=True)
def rd_func_random_case(context, parts):
    for part in parts: yield ''.join(
        c.upper() if random.randrange(2) else c.lower() for c in part)

@rd_func('hyphenate', 'hy', unicode=True)
def rd_func_hyphenate(context, parts):
    for part in parts: yield re.sub(r'\s+', '-', part, flags=re.U)

@rd_func('underscore', 'us', unicode=True)
def rd_func_hyphenate(context, parts):
    for part in parts: yield re.sub(r'\s+', '_', part, flags=re.U)

@rd_func('remove-spaces', 'rs', unicode=True)
def rd_func_remove_spaces(context, parts):
    for part in parts: yield re.sub(r'\s+', '', part, flags=re.U)

@rd_func('remove-punctuation', 'rp', unicode=True)
def rd_func_remove_punctuation(context, parts):
    for part in parts: yield re.sub(r'([^\w\s]|_)+', '', part, flags=re.U)

#===============================================================================
# Maintenance of global definitions.

def load_defs():
    if not os.path.exists(DEF_FILE):
        return {}
    with open(DEF_FILE, 'r') as file:
        jdict = util.recursive_encode(json.load(file), 'utf8')
        return {c: GlobalDefs(jdict=d) for (c,d) in jdict.iteritems()}

def save_defs(backup=True):
    prune_defs()
    jstring = json.dumps({
        c: d.save_jdict() for (c,d) in global_defs.iteritems()},
        separators=(',', ':'))

    if backup:
        if not os.path.exists(os.path.dirname(DEF_BACKUP_NAME)):
            os.mkdir(os.path.dirname(DEF_BACKUP_NAME))
        prev_name = None
        for n in xrange(DEF_BACKUPS, -1, -1):
            name = (DEF_BACKUP_NAME % n) if n > 0 else DEF_FILE
            # To prevent floods of changes from destroying all viable backups,
            # the oldest, 2nd-oldest, and 3rd-oldest backups are only replaced
            # by files newer than them by resp. 1 day, 1 hour, and 5 minutes.
            # (Unless DEF_BACKUPS < 4, in which case the 4th-, 3rd- and
            # 2nd-newest backups, when they exist, assume these roles.)
            min_d = 86400 if n == max(3, DEF_BACKUPS-1) else \
                     3600 if n == max(2, DEF_BACKUPS-2) else \
                      300 if n == max(1, DEF_BACKUPS-3) else None
            if os.path.exists(name) and prev_name is not None \
            and (not os.path.exists(prev_name) \
            or os.stat(name).st_mtime - os.stat(prev_name).st_mtime > min_d):
                os.rename(name, prev_name)
            prev_name = name

    if not os.path.exists(os.path.dirname(DEF_FILE)):
        os.mkdir(os.path.dirname(DEF_FILE))

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

class DictStack(object, DictMixin):
    __slots__ = 'stack'
    def __init__(self, *stack):
        self.stack = stack
    def __getitem__(self, key):
        for dict in self.stack:
            if key in dict:
                return dict[key]
        raise KeyError
    def __iter__(self):
        for i in xrange(len(self.stack)):
            for key in self.stack[i]:
                if all(key not in self.stack[j] for j in xrange(i)):
                    yield key

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
    __slots__ = 'name', '_body_str', '_body_ast'
    def __init__(self, name='', body_str=None, body_ast=None):
        self.name = name
        self._body_str = body_str
        self._body_ast = body_ast

    @property
    def body_str(self):
        return self._body_str if self._body_str is not None else \
               str(self._body_ast.source) if self._body_ast is not None else \
               None

    @property
    def body_ast(self):
        return self._body_ast if self._body_ast is not None else \
               parse_string(self._body_str) if self._body_str is not None else \
               None

    def postprocess(self, str_iter, context=None):
        return str_iter
    postprocess.is_identity = True

class GlobalDef(Def):
    __slots__ = 'id', 'modes', 'time'
    def __init__(self, id=None, modes=None, time=None, jdict=None, *a, **k):
        if jdict is None:
            super(GlobalDef, self).__init__(*a, **k)
            self.id, self.modes, self.time = id, modes, time
        else:
            super(GlobalDef, self).__init__(*a, body_str=jdict.get('body'), **k)
            self.id = util.ID(*jdict['id']) if 'id' in jdict else None
            self.modes = jdict.get('modes')
            self.time = jdict.get('time')
    def save_jdict(self):
        jdict = {'body': self.body_str}
        if self.id is not None:
            jdict['id'] = list(self.id)
        if self.modes is not None:
            jdict['modes'] = self.modes
        if self.time is not None:
            jdict['time'] = self.time
        return jdict

# Definitions usable by a user by private message.
class PrivateDefs(DictStack):
    def __init__(self, id):
        key = ('%s!%s@%s' % id).lower()
        stack = [UserChannelDefs(id)]
        if key in global_defs:
            stack.insert(0, global_defs[key])
        super(PrivateDefs, self).__init__(*stack)

# Definitions from channels a user is in, where the most recently changed
# definition takes priority in case of a name collision.
class UserChannelDefs(DictMixin):
    __slots__ = 'id'

    def __init__(self, id):
        self.id = id

    def __getitem__(self, key):
        defn = None
        for chan, nicks in channel.track_channels.iteritems():
            if chan.lower() in global_defs and key in global_defs[chan.lower()] \
            and any(self.id.nick.lower() == n.lower() for n in nicks):
                chan_defn = global_defs[chan.lower()][key]
                if defn is None or chan_defn.time > defn.time:
                    defn = chan_defn
        if defn is None:
            raise KeyError
        return defn

    def __iter__(self):
        for chan, nicks in channel.track_channels.iteritems():
            if chan.lower() in global_defs \
            and any(self.id.nick.lower() == n.lower() for n in nicks):
                for key in global_defs[chan.lower()]:
                    yield key

# Automatic definitions provided in addition to, and possibly derived from, an
# iterable dict-like container of underlying definitions. Not iterable.
class AutoDefs(DictStack):
    def __init__(self, base_defs):
        if base_defs is not None:
            super(AutoDefs, self).__init__(base_defs, CaseAutoDefs(base_defs))
        else:
            super(AutoDefs, self).__init__()
    def __iter__(self):
        raise NotImplementedError('AutoDefs instances are not iterable.')

# Class of AutoDefs consisting of case transformations applied to the results of
# definitions based on corresponding transformations to their names. For example,
# looking up 'BEVERAGE' when there is a definition named 'beverage' will return
# a virtual definition which turns the results of 'beverage' into all uppercase.
class CaseAutoDefs(object, DictMixin):
    __slots__ = '_base_defs'
    def __init__(self, base_defs):
        self._base_defs = base_defs
    def __getitem__(self, key):
        base_keys = sorted(b for b in self._base_defs if b.lower() == key.lower())
        if key in base_keys: return self._base_defs[key]
        if not base_keys: raise KeyError
        base_key = min(base_keys, key=lambda b: sum(1 for c in b if c.isupper()))
        return CaseAutoDef(self._base_defs[base_key], base_key, key)

# A virtual definition produced by CaseAutoDefs.
class CaseAutoDef(Def):
    __slots__ = '_old_key', '_new_key'

    def __init__(self, base, old_key, new_key):
        self._old_key, self._new_key = old_key, new_key
        super(CaseAutoDef, self).__init__(
            name=new_key, body_ast=base._body_ast, body_str=base._body_str)

    def postprocess(self, str_iter, context=None):
        def decoded():
            for part in str_iter:
                if not part: continue
                try: yield part.decode('utf8') if type(part) is str else part
                except UnicodeDecodeError: yield part
        for part in self.postprocess_(decoded(), context):
            yield part.encode('utf8') if type(part) is unicode else part

    def postprocess(self, str_iter, context):
        old = ''.join(c for c in self._old_key if c.isupper() or c.islower())
        new = ''.join(c for c in self._new_key if c.isupper() or c.islower())
        assert new != old

        if new.isupper() and not old.isupper():
            return rd_func_uppercase(context, str_iter)
        elif new.islower() and not old.islower():
            return rd_func_lowercase(context, str_iter)
        elif new[0].isupper() and old[0].islower() and new[1:] == old[1:]:
            return rd_func_initial_capital(context, str_iter)
        else:
            return rd_func_title_case(context, str_iter)

global_defs = load_defs()

#-------------------------------------------------------------------------------
@link(('HELP', 'roll-def'), ('HELP', 'rd'))
@link(('HELP', 'roll+'), ('HELP', 'roll-'), ('HELP', 'roll?'))
@link(('HELP', 'r+'), ('HELP', 'r-'), ('HELP', 'r?'))
def h_help_roll_def(bot, reply, args):
    reply(None, 'See: \2!help rd+\2, \2!help rd-\2, and \2!help rd?\2.')

@link('!roll-def', cmd='!roll-def')
@link('!rd',       cmd='!rd', pre='\2!r\2, ')
def h_roll_def(bot, id, target, args, full_msg, cmd, pre=''):
    message.reply(bot, id, target, 'This is not a valid command. Perhaps you'
    ' meant: %(pre)s\2%(cmd)s+\2, \2%(cmd)s-\2, or \2%(cmd)s?\2.'
    % {'cmd': cmd, 'pre': pre})

@link('!r+', cor='!rd+')
@link('!r-', cor='!rd-')
@link('!r?', cor='!rd?')
@link('!roll+', cor='!roll-def+')
@link('!roll-', cor='!roll-def-')
@link('!roll?', cor='!roll-def?')
def h_roll_suf(bot, id, target, args, full_msg, cor):
    message.reply(bot, id, target, 'This is not a valid command. Perhaps you'
    ' meant: \2%s\2.' % cor)

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
    if len(name) > DEF_MAX_NAME_LEN or not re.match(r'(?!\d)[\w-]+$', name):
        return message.reply(bot, id, target, 'Error: you must specify a name'
        ' consisting of letters, digits, \2-\2 and \2_\2, not starting with a'
        ' digit and no longer than %d characters. See \2!help roll-def+\2 for'
        ' correct usage.' % DEF_MAX_NAME_LEN)

    if name in RESERVED_NAMES: return message.reply(bot, id, target,
        'Error: the name "%s" is reserved for special use and may not be'
        ' defined.' % name)

    if sum(len(d) for d in global_defs.itervalues()) >= DEF_MAX_TOTAL:
        return message.reply(bot, id, target, 'Error: there are too many defin'
        'itions stored. Please notify the bot administrator of this message.')

    body_ast = parse_string(body)
    body = str(body_ast.source)
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

        for node in traverse_ast(body_ast, Name):
            if node.namespace is not None: return message.reply(bot, id, target,
            'Error: "%s" is illegal: references specifying a source channel may'
            ' not occur in channel roll definitions.'
            % abbrev_middle(str(node.source)))

        is_op = channel.has_op_in(bot, id.nick, chan, 'h')
        udefs = None if is_op else \
                sum(1 for d in defs.itervalues() if util.same_user(d.id, id))
        modes = channel.umode_channels[chan].get(id.nick.lower(), '')

    if name not in defs and udefs is not None and udefs >= DEF_MAX_PER_USER:
        return message.reply(bot, id, target, 'Error: you have made too many'
        ' definitions here - no more than %d are permitted. See \2!help'
        ' roll-def-\2 to delete existing definitions.' % DEF_MAX_PER_USER)

    def_id = defs[name].id if name in defs else id
    def_modes = defs[name].modes if name in defs else \
                modes if target is not None else None

    defs[name] = GlobalDef(
        name=name, id=def_id, modes=def_modes, time=now, body_str=body)
    defs.touch()
    global_defs[chan] = defs
    save_defs()

    msg = 'Defined.'
    odefs = sorted(o for o in defs if o.lower() == name.lower() and o != name)
    if odefs:
        ostr = '\2, \2'.join(odefs[:-2] + ['\2 and \2'.join(odefs[-2:])])
        msg += (' (Note: the definition%s \2%s\2, which %s distinct from'
                ' \2%s\2, %s unchanged.)' % (('s', ostr, 'are', name, 'were')
                if len(odefs) > 1 else ('', ostr, 'is', name, 'was')))

    message.reply(bot, id, target, msg)

#-------------------------------------------------------------------------------
@link(('HELP', 'roll-def-'), ('HELP', 'rd-'))
def h_help_roll_def_m(bot, reply, args):
    reply('!roll-def-\2 or \2!rd- NAME1 [NAME2 ...]',
    'Delete the definitions made using \2!rd+\2 of each given NAME. If the user'
    ' is not a channel operator, only definitions originally made by the same'
    ' user will be deleted. Each NAME may contain wildcard characters \2?\2 and'
    ' \2*\2, may consist of a hostmask, or may may be preceded by \2!\2 to'
    ' prevent its deletion, as in \2!rd?\2. All names are case-sensitive. See'
    ' also: \2!help rd+\2, \2!help rd?\2.')

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
            if util.same_user(id, defn.id):
                ddefs.append(defn)
            else:
                udefs.append(defn)

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
        return roll_def_query(bot, id, target, args, chan, chan_case, external=True)

    elif target is not None:
        chan = target.lower()
        chan_case = channel.capitalisation.get(chan, target)
        return roll_def_query(bot, id, target, args, chan, chan_case)

    chan_case = '%s!%s@%s' % id
    chan = chan_case.lower()
    if chan in global_defs:
        global_defs[chan].touch()
    if args:
        count = roll_def_query(
            bot, id, target, args, chan, chan_case,
            multiple=True, skip_empty=True)
        for ex_chan, nicks in channel.track_channels.iteritems():
            if all(n.lower() != id.nick.lower() for n in nicks): continue
            ex_chan_case = channel.capitalisation.get(ex_chan, ex_chan)
            count += roll_def_query(
                bot, id, target, args, ex_chan, ex_chan_case,
                external=True, skip_empty=True, multiple=True)
        if count == 0:
            roll_def_query(bot, id, target, args, chan, chan_case, multiple=True)
    else:
        roll_def_query(bot, id, target, args, chan, chan_case)

def roll_def_query(
    bot, id, target, args, chan, chan_case, external=False, skip_empty=False,
    multiple=False
):
    defs = list(def_search(chan, args, match_case=False))
    if skip_empty and not defs: return 0

    private = not chan.startswith('#')
    s = 's' if len(defs) != 1 else ''
    noun = 'definition%s' % s if multiple or not private and not external else \
           'definition%s in %s' % (s, chan_case) if not private else \
           'private definition%s' % s
    if args:
        noun = 'matching %s' % noun
    defs_str = '%d %s' % (len(defs), noun) if not multiple else \
               '\2Private:\2 %d %s' % (len(defs), noun) if private else \
               '\2%s:\2 %d %s' % (chan_case, len(defs), noun)

    if len(defs) == 0:
        chan_defs = sum(
            len(defs) for chan, defs in global_defs.iteritems() if defs
            and id.nick.lower() in map(str.lower, channel.track_channels[chan]))
        suffix = ' Use \2!rd? *\2 to view definitions in all of your channels' \
                 ' or \2!rd? #CHANNEL\2 for those in a particular channel.' \
                 if private and chan_defs and not args else ''
        message.reply(bot, id, target, '%s.%s' % (defs_str, suffix), prefix=False)
    elif len(defs) == 1:
        defn = defs[0]
        if defn.time is not None:
            dt_set = datetime.datetime.utcfromtimestamp(defn.time)
            delta = datetime.datetime.utcnow() - dt_set
            d_mins, d_secs = divmod(delta.seconds, 60)
            d_hours, d_mins = divmod(d_mins, 60)
            time_str = ', last changed %s UTC (%sd, %02d:%02d:%02d ago)' % (
                dt_set.strftime('%d %b %Y, %H:%M'),
                delta.days, d_hours, d_mins, d_secs)
        else:
            time_str = ''
        if defn.modes:
            def_mnick = channel.modes_prefix_nick(bot, defn.id.nick, defn.modes)
            def_id = def_mnick, defn.id.user, defn.id.host
        else:
            def_id = defn.id
        message.reply(bot, id, target,
            '%s%s%s:' % (
                defs_str,
                (', set by %s!%s@%s' % def_id) if chan.startswith('#') else '',
                time_str),
            prefix=False)
        message.reply(bot, id, target,
            '    %s = %s' % (defn.name, defn.body_str), prefix=False)
    elif len(defs) <= 3 and not multiple:
        message.reply(bot, id, target, '%s:' % defs_str, prefix=False)
        rows = util.join_rows(*((d.name, d.body_str) for d in defs), sep=' = ')
        for row in rows:
            message.reply(bot, id, target, '    %s' % row, prefix=False)
    else:
        parts = ['%s:' % defs_str]
        parts += [nm + ('.' if ix == len(defs)-1 else ',') for (nm, ix)
                  in izip((df.name for df in defs), count())]
        parts += ['' if multiple else 'Use \2!rd?%s NAME\2 to view the details'
                  ' of a definition.' % ((' %s' % chan_case) if external
                  and not (target and target.lower() == chan) else '')]
        i = 0
        while i < len(parts):
            len_sum = 0
            for j in xrange(i, len(parts)):
                len_sum += len(parts[j]) + (1 if j > i else 0)
                if j > i and len_sum > MAX_MESSAGE_LENGTH: break
            else: j = len(parts)
            prefix = '... ' if i > 0 else ''
            suffix = ' ...' if j < len(parts) else ''
            msg = prefix + ' '.join(parts[i:j]) + suffix
            message.reply(bot, id, target, msg, prefix=False)
            i = j

    return len(defs)

# An iterator over the definitions matched by `queries' as per !rd? and !rd-,
# sorted according to (1) the position of the first matching positive query in the
# sequence, and (2) by the case-insensitive name of the definition.
def def_search(chan, queries, *args, **kwds):
    pos, neg = [], []
    for query in queries:
        if query.startswith('!'):
            neg.append(query[1:])
        else:
            pos.append(query)
    if not pos:
        pos.append('*')

    results = []
    for defn_name, defn in global_defs.get(chan, {}).iteritems():
        if any(def_match(neg_q, d, *args, **kwds) for neg_q in neg):
            continue
        for pos_q, pos_q_index in izip(pos, count()):
            if def_match(pos_q, defn, *args, **kwds):
                sort_key = (pos_q_index, defn_name.lower(), defn_name)
                results.append((defn, sort_key))
                break

    return (d for (d,_) in sorted(results, key=lambda t: t[1]))

# True iff `query' positively matches `defn' as per !rd? and !rd-.
def def_match(query, defn, match_case=True):
    if '!' in query or '@' in query:
        id_str = ('%s!%s@%s' % defn.id) if defn.id is not None else '*!*@*'
        return re.match(util.wc_to_re(query), id_str, flags=re.I) is not None
    else:
        flags = 0 if match_case else re.I
        return re.match(util.wc_to_re(query), defn.name, flags=flags) is not None

#===============================================================================
# Miscellaneous utilities:

def abbrev_middle(str, max_len=50, mark='(...)'):
    if len(str) <= max_len: return str
    left_len = (max_len - len(mark))/2
    right_len = (max_len - len(mark)) - left_len
    return str[:left_len] + mark + str[-right_len:]

def abbrev_right(str, max_len=50, mark='(...)'):
    if len(str) <= max_len: return str
    return str[:max_len-len(mark)] + mark

def traverse_ast(node, *types):
    if type(node) in types:
        yield node
    if type(node) is String:
        for part in node.parts:
            for t_node in traverse_ast(part, *types): yield t_node
    elif type(node) in (Expr, TermKeep) and any(t in (
    Expr, TermDice, TermDiceC, TermDiceD, TermKeep, TermCnst) for t in types):
        if type(node) is Expr:
            for t_node in traverse_ast(node.term, *types): yield t_node
        for t_node in traverse_ast(node.expr, *types): yield t_node
    elif type(node) is Branch:
        for choice in node.choices:
            for t_node in traverse_ast(choice, *types): yield t_node
    elif type(node) is Choice:
        for t_node in traverse_ast(node.string, *types): yield t_node
    elif type(node) is NameApp and Name in types:
        for t_node in traverse_ast(node.name, *types): yield t_node
        for suffix in node.suffixes:
            for t_node in traverse_ast(suffix, *types): yield t_node
    elif type(node) is StringApp:
        for t_node in traverse_ast(node.string, *types): yield t_node
        if Name in types:
            for suffix in node.suffixes:
                for t_node in traverse_ast(suffix, *types): yield t_node
