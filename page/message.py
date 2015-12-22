from untwisted.magic import sign
from util import LinkSet, ID
from util import message_reply as reply
from itertools import *
import inspect
import util
import re

import limit

IGNORE_FILE = 'conf/ignore.txt'

link, install, uninstall = LinkSet().triple()

try:
    with open(IGNORE_FILE) as file:
        ignore_re = '|'.join(
            '(%s)' % util.wc_to_re(line)
            for raw_line in file for line in [raw_line.strip()] if line)
        ignore_re = re.compile(ignore_re, re.I) if ignore_re else None
except IOError:
    ignore_re = None

@link('XIRCLIB_EVENT')
def h_xirclib_msg(event, bot, source, *args):
    if ignore_re and isinstance(source, tuple) \
    and ignore_re.match('%s!%s@%s' % source):
        return    
    yield sign(event, bot, source, *args)

@link('COMMAND',        action=False)
@link('ACTION_COMMAND', action=True)
def h_command(bot, id, target, event, body, message, action):
    if limit.mark_activity(bot, id, notify=target):
        return
    if action:
        event = ('ACTION', event)
    yield sign(event, bot, id, target, body, message)

@link('JOIN')
def join(bot, source, chans, *args):
    id = ID(*source)
    for chan in chans.split(','):
        yield sign('SOME_JOIN', bot, id, chan)
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_JOIN', bot, chan)
        else:
            yield sign('OTHER_JOIN', bot, id, chan)

@link('PART')
def part(bot, source, chans, msg=None, *args):
    id = ID(*source)
    for chan in chans.split(','):
        yield sign('SOME_PART', bot, id, chan, msg)
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_PART', bot, chan, msg)
            yield sign('SELF_PART_FINAL', bot, chan, msg)
        else:
            yield sign('OTHER_PART', bot, id, chan, msg)
            yield sign('OTHER_PART_FINAL', bot, id, chan, msg)

@link('KICK')
def kicked(bot, op_id, chan, other_nick, msg=None, *args):
    op_id = ID(*op_id)
    yield sign('SOME_KICKED', bot, other_nick, op_id, chan, msg)
    if (other_nick.lower() == bot.nick.lower()):
        yield sign('SELF_KICKED', bot, chan, op_id, msg)
        yield sign('SELF_KICKED_FINAL', bot, chan, op_id, msg)
    else:
        yield sign('OTHER_KICKED', bot, other_nick, op_id, chan, msg)
        yield sign('OTHER_KICKED_FINAL', bot, other_nick, op_id, chan, msg)

@link('QUIT')
def quit(bot, source, msg=None, *args):
    id = ID(*source)
    if (id.nick.lower() == bot.nick.lower()):
        yield sign('SELF_QUIT', bot, msg)
    else:
        yield sign('OTHER_QUIT', bot, id, msg)

@link('NICK')
def nick(bot, id, new_nick, *args):
    id = ID(*id)
    if id.nick.lower() == bot.nick.lower():
        yield sign('SELF_NICK', bot, new_nick)
        bot.nick = new_nick
    else:
        yield sign('OTHER_NICK', bot, id, new_nick)
    yield sign('SOME_NICK', bot, id, new_nick)

@link('PRIVMSG')
def privmsg(bot, source, target, msg, *args):
    if target.lower() == bot.nick.lower(): target = None
    if type(source) == tuple:
        id = ID(*source)
        bot.activity = False
        yield sign('MESSAGE', bot, id, target, msg)
        if bot.activity: return
        yield sign('MESSAGE_IGNORED', bot, id, target, msg)
    elif type(source) == str:
        yield sign('SMESSAGE', bot, source, target, msg)

@link('NOTICE')
def notice(bot, source, target, msg, *args):
    if target == bot.nick: target = None
    if type(source) == tuple:
        id = ID(*source)
        yield sign('UNOTICE', bot, id, target, msg)
    elif type(source) == str:
        yield sign('SNOTICE', bot, source, target, msg)

@link('MESSAGE')
def message(bot, id, target, msg):
    while True:
        match = re.match(r'\x01ACTION (.*?)\x01?$', msg)
        if match:
            msg = match.group(1)
            action = True
        else:
            action = False

        # !CMD [ARGS...]
        if bot.conf['bang_cmd']:
            match = re.match(r'!(?P<head>\S*)\s*(?P<body>.*)', msg)
            if match: break

        # NICK: CMD [ARGS...]
        match = re.match(r'(?P<addr>\S+):\s*!?(?P<head>\S*)\s*(?P<body>.*)', msg)
        if match and match.group('addr').lower() == bot.nick.lower(): break

        return
    
    event = '!' + match.group('head').lower()
    body = match.group('body').strip()
    type = 'ACTION_COMMAND' if action else 'COMMAND'
    yield sign(type, bot, id, target, event, body, msg)
    bot.activity = True

    from untwisted.usual import Stop
    raise Stop


@link('HELP*')
def h_help_help_short(bot, reply, args):
    reply('help [COMMAND]',
    'Gives detailed information about COMMAND, or lists all commands.')

@link(('HELP', 'help'))
def h_help_help(bot, reply, args):
    reply('help [COMMAND]',
    'If COMMAND is given, gives detailed information about its usage;'
    ' otherwise, gives a summary of all available commands.')

@link('!help')
@link('!commands')
def h_help(bot, id, target, args, full_msg):
    lines = []
    callback = lambda *args: lines.append(args)
    output = lambda msg: bot.send_msg(target or id.nick, msg)

    def header(str):
        return '\2%s%s\2' % ('!' if bot.conf['bang_cmd'] else '', str)

    if args:
        # Display help for a particular command.
        cmd, args = re.match(r'!?(\S+)\s*(.*)', args).groups()
        yield sign(('HELP', cmd.lower()), bot, callback, args)
        if not lines:
            reply(bot, id, target,
                'Error: no help is available for "%s".' % cmd)
            return
        for line in lines:
            if line[0]: output(header(line[0]))
            for para in line[1:]:
                if para: output(para)
    else:
        # Display general help and a summary of all commands.
        output(
            'Commands are issued by saying%s "%s: COMMAND",'
            ' where COMMAND is the command and its parameters.'
            ' The following commands are available:'
            % (' "!COMMAND" or' if bot.conf['bang_cmd'] else '', bot.nick))

        yield sign('HELP*', bot, callback, args)
        lines = map(lambda l: (header(l[0]),) + l[1:], lines)
        map(output, util.align_table(lines))

        del lines[:]
        yield sign('HELP', bot, callback, args)
        if lines: output('Other commands: %s.' % ', '.join(
            '\2%s\2' % l[0].split()[0] for l in lines))
