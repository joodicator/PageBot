# coding=utf8

import re

from message import reply
import util

link, install, uninstall = util.LinkSet().triple()

#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('convert QUANTITY [to] UNIT',
    'Convert between measurement systems.')

@link(('HELP', 'convert'))
def h_help_convert(bot, reply, args):
    reply('convert QUANTITY [to] UNIT')
    reply('cv QUANTITY [to] UNIT',
    'Convert a quantity expressed in a certain unit to another unit of'
    ' measurement. Currently, the following units are supported: metre, inch,'
    ' foot, yard, mile, nautical mile, league, Planck length; gram, ounce,'
    ' pound, stone, Planck mass; degree Celsius, Farenheit, Kelvin, Rankine.'
    ' SI prefixes may be used with suitable metric units. Standard'
    ' abbreviations may be used.')

#-------------------------------------------------------------------------------
@link('!convert', '!cv')
def h_convert(bot, id, target, args, full_msg):
    try:
        reply(bot, id, target, convert_report(args))
    except UserError as e:
        reply(bot, id, target, 'Error: %s' % e.message)

def convert_report(str):
    x, y, xu, yu = convert(str)
    return '%s = %s' % (xu.format_unit(x), yu.format_unit(y))

#-------------------------------------------------------------------------------
# Returns (from_value, to_value, from_unit, to_unit)
def convert(str):
    x_re = r'((\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'

    m = re.match(r'(?i)(?!%s)(?P<u1>.*?)(?P<x>%s)(\s+to\s+)?(?P<u2>.+)'
            % (x_re, x_re), str) or \
        re.match(r'(?i)(?P<x>%s)(?P<u1>.*)\s+to\s+(?P<u2>.+)' % x_re, str) or \
        re.match(r'(?P<x>%s)\s*(?P<u1>\S*)\s+(?P<u2>\S+)\s*$' % x_re, str)
    if m:
        x = float(m.group('x'))
        u1 = parse_unit_full(m.group('u1').strip())
        u2 = parse_unit_full(m.group('u2').strip())

    if not m:
        m = re.match(r'(?P<x>%s)(?P<us>.*)' % x_re, str)
        if m:
            x = float(m.group('x'))
            u1, rest = parse_unit_part(m.group('us').strip())
            u2 = parse_unit_full(rest.strip())

    if not m:
        raise UserError('unrecognised syntax.')

    return (x, convert_value(x, u1, u2), u1, u2)

#===============================================================================
def convert_value(x, u1, u2):
    if u1.dim != u2.dim: raise UserError('cannot convert %s (%s) to %s (%s).'
        % (u1.format_unit(x), u1.dim, u2.name, u2.dim))
    return u1.convert_to(u2, x)

# Returns (unit, str_remain)
def parse_unit_part(str):
    result = parse_unit(str)
    if not result: raise UserError('unrecognised syntax.')
    return result[0]

# Returns unit
def parse_unit_full(str):
    if not str: return Number()
    for result in parse_unit(str):
        (unit, rest) = result
        if not rest: return unit
    raise UserError('"%s" is not a recognised unit.' % str)

# Returns [(unit, str_remain), ...]
def parse_unit(str):
    us = []
    for U in Temp, Dist, Mass:
        u = U.parse_unit(str)
        if u: us.append(u)
    return sorted(us, key=lambda (u,s): len(s))

#===============================================================================
class UserError(Exception):
    pass

#===============================================================================
class Unit(object):
    def convert_to(self, unit, x):
        if unit.dim != self.dim: raise Exception()
        return unit.fr_base(self.to_base(x))

    def format_value(self, x):
        return '%.4g' % x

    def __repr__(self):
        return '<%s:%s>' % (self.dim, self.name)

class MUnit(Unit):
    def __init__(self, name, mult):
        self.name = name
        self.format_unit = lambda x: '%s %s' % (self.format_value(x), name)
        self.to_base = lambda x: x*mult
        self.fr_base = lambda x: x/mult

#===============================================================================
class Number(Unit):
    dim = 'dimensionless'
    name = 'number'
    def to_base(self, x):
        return x
    def fr_base(self, x):
        return x    
    def format_unit(self, x):
        return self.format_value(x)

#===============================================================================
class Temp(Unit):
    dim = 'temperature'
    def __init__(self, name, k0, k1):
        self.name = name
        self.format_unit = lambda x: '%s%s' % (self.format_value(x), name)
        self.to_base = lambda x: (x - k0)/k1
        self.fr_base = lambda x: k0 + x*k1

    @classmethod
    def parse_unit(cls, str):
        m = re.match(r'(?i)(°|deg(rees?)?)\s*'
            r'(?P<u>(k(elvin)?|r(ankine)?|c(elsius)?)|f(arenheit))', str) or \
            re.match(r'(?P<u>K|R|C|F)', str)
        if not m: return
        u = Temp('°K',    0,    1  ) if m.group('u')[0].lower() == 'k' else \
            Temp('°R',    0,    1.8) if m.group('u')[0].lower() == 'r' else \
            Temp('°C', -273.15, 1  ) if m.group('u')[0].lower() == 'c' else \
            Temp('°F', -459.67, 1.8) if m.group('u')[0].lower() == 'f' else None
        if u: return (u, str[m.end():])

#===============================================================================
class Dist(MUnit):
    dim = 'length'

    @classmethod
    def parse_unit(cls, str):
        m = re.match(r'(?i)(?P<u>(inch(es)?|f(oo|ee)t|yards?|miles?'
                r'|Planck lengths?|leagues?|nautical miles?))', str) or \
            re.match(r'(?i)(?P<p>%s)?\s*(?P<u>(met(re|er)s?))' % SI_CI_RE, str) or \
            re.match(r'(?P<u>(in|ft|yds?|mi|NM))', str) or \
            re.match(r'(?P<p>%s)?\s*(?P<u>m)' % SI_CS_RE, str)
        if m:
            n = m.group('u')
            u = Dist('m', 1) if \
                    n=='m' or n.lower().startswith('me') else \
                Dist('in', 0.0254) if \
                    n.lower().startswith('in') else \
                Dist('ft', 0.3048) if \
                    n.lower() in ('foot','feet','ft') else \
                Dist('yd', 0.9144) if \
                    n.lower().startswith('yard') or n in ('yd','yds') else \
                Dist('mi', 1609.344) if \
                    n.lower().startswith('mi') else \
                Dist('nautical mile(s)', 1852) if \
                    n.lower().startswith('nautical') or n=='NM' else \
                Dist('league(s)', 3*1609.344) if \
                    n.lower().startswith('league') else \
                Dist('Planck length(s)', 1.61619997e-35) if \
                    n.lower().startswith('planck') else None
            if m.groupdict().get('p'): u = SI(u, *si_info(m.group('p')))
            if u: return (u, str[m.end():])

#===============================================================================
class Mass(MUnit):
    dim = 'mass'

    @classmethod
    def parse_unit(cls, str):
        m = re.match(r'(?i)(?P<p>%s)?\s*(?P<u>gram(me)?s?)' % SI_CI_RE, str) or \
            re.match(r'(?i)(?P<u>(ounces?|pounds?|stones?|planck mass(es)?))', str) or \
            re.match(r'(?P<p>%s)?\s*(?P<u>g)' % SI_CS_RE, str) or \
            re.match(r'(?P<u>(oz|lbs?|st))', str)
        if m:
            n = m.group('u')
            if n.lower().startswith('g'):
                u = Mass('g', 1)
            elif n.lower().startswith('o'):
                u = Mass('oz', 28.349523125)
            elif n.lower().startswith('planck'):
                u = Mass('Planck mass', 2.1765113e-5)
            elif n.lower().startswith('p') or n.startswith('lb'):
                u = Mass('lb', 0.45359237)
            elif n.lower().startswith('st'):
                u = Mass('st', 0.00635)
            if m.groupdict().get('p'): u = SI(u, *si_info(m.group('p')))
            if u: return (u, str[m.end():])

#===============================================================================
SI_PREFIXES = [
    ('yocto', 'y',     -24),    ('yotta', 'Y',  24),
    ('zepto', 'z',     -21),    ('zetta', 'Z',  21),
    ('atto',  'a',     -18),    ('exa',   'E',  18),
    ('femto', 'f',     -15),    ('peta',  'P',  15),
    ('pico',  'p',     -12),    ('tera',  'T',  12),
    ('nano',  'n',     -9),     ('giga',  'G',  9),
    ('micro', 'µ|μ|u', -6),     ('mega',  'M',  6),
    ('milli', 'm',     -3),     ('kilo',  'k',  3),
    ('centi', 'c',     -2),     ('hecto', 'h',  2),
    ('deci',  'd',     -1),     ('deca',  'da', 1)]

SI_CS_RE = '(%s)' % '|'.join(s for (i,s,e) in SI_PREFIXES)
SI_CI_RE = '(%s)' % '|'.join(i for (i,s,e) in SI_PREFIXES)

# Returns (name, exponent)
def si_info(prefix):
    for (ci_re, cs_re, exp) in SI_PREFIXES:
        if re.match(ci_re, prefix, re.I) or re.match(cs_re, prefix):
            return (cs_re.split('|')[0], exp)

class SI(Unit):
    def __init__(self, sub, pre, exp):
        self.dim = sub.dim
        self.name = '%s%s' % (pre, sub.name)
        self.format_unit = lambda x: \
            '%s %s%s' % (self.format_value(x), pre, sub.name)
        self.to_base = lambda x: sub.to_base(x * 10**exp)
        self.fr_base = lambda x: sub.fr_base(x) / 10**exp
