from untwisted.utils.common import shrug, append
from untwisted.network import *
from untwisted.event import *

import re

RFC_STR = "^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?"
RFC_REG = re.compile(RFC_STR)

PREFIX_STR = "(?P<nick>.+)!(?P<user>.+)@(?P<host>.+)"
PREFIX_REG = re.compile(PREFIX_STR)

#ARGUMENT_STR = "[^: ]+|:.+"

#this regex was suggested by joo
ARGUMENT_STR = ":(.*)|(\S+)"
ARGUMENT_REG = re.compile(ARGUMENT_STR)

CTCP_STR = "[^ ]+"
CTCP_REG = re.compile(CTCP_STR)

empty = lambda data: data if data else ''

def install(obj):
    obj.link(DATA, append)
    obj.link(BUFFER, shrug)
    obj.link(FOUND, main)
    #obj.link('PRIVMSG', extract_ctcp) 
    #obj.link('DCC', patch) 

def main(work, data):
    field    = re.match(RFC_REG, data)

    if not field:
        return

    prefix   = extract_prefix(field.group('prefix'))
    command  = field.group('command').upper()
    argument = extract_argument(field.group('argument'))

    yield sign('XIRCLIB_EVENT', command, work, prefix, *argument)

def extract_prefix(prefix):
    field = re.match(PREFIX_REG, empty(prefix))

    if not field:
        return prefix

    return field.group(1, 2, 3)

def extract_argument(argument):
    return tuple(
        m.group(1) or m.group(2)
        for m in re.finditer(ARGUMENT_REG, empty(argument)))

'''
def extract_ctcp(*args):
    DELIM = '\001'
    msg = args[-1].lstrip(':') 

    if not msg.startswith(DELIM) or not msg.endswith(DELIM):
        return

    msg = msg.strip(DELIM)
    field = re.findall(CTCP_REG, msg) 

    yield sign(field[0], *(args[:-1] + tuple(field[1:])))

def patch(*args):
    yield sign('DCC %s' % args[5],  *(args[:5] + args[6:]))
'''
