from untwisted.magic import sign
from util import LinkSet, ID
from util import message_reply as reply
from itertools import *
import inspect
import util
import re

import limit

link, install, uninstall = LinkSet().triple()

@link('XIRCLIB_EVENT')
def h_xirclib_msg(event, bot, source, *args):
    if type(source) is tuple:
        source = ID(*source)
    yield sign(event, bot, source, *args)

@link('COMMAND',        action=False)
@link('ACTION_COMMAND', action=True)
def h_command(bot, id, target, event, body, full_msg, action):
    bot.activity = False

    #=================================================================
    # (This should be in bridge.py.)
    s_event = ('SIMPLE', 'ACTION', event) if action else \
              ('SIMPLE',           event)
    no_echo = [False]
    replies = []
    def cmd_reply(rmsg=None, from_name=None, no_bridge=False, **kwds):
        if rmsg is not None or from_name is not None:
            if rmsg is None: rmsg = from_name(id.nick)
            replies.append(((bot, id, target, rmsg), kwds))
        no_echo[0] = no_echo[0] or no_bridge
    yield sign(s_event, bot, id.nick, target, body, cmd_reply)
    if not no_echo[0]:
        cmsg = ('* %s %s' if action else '<%s> %s') % (id.nick, full_msg)
        yield sign('IRC', bot, target, cmsg)
    for rargs, rkwds in replies:
        reply(*rargs, **rkwds)       
    #=================================================================
        
    if limit.mark_activity(bot, id, notify=target):
        return
    if action:
        event = ('ACTION', event)
    yield sign(event, bot, id, target, body, full_msg)
    if bot.activity: return
    yield sign('CMD_IGNORED', event, bot, id, target, body, full_msg)

@link('JOIN')
def join(bot, id, chans, *args):
    for chan in chans.split(','):
        yield sign('SOME_JOIN', bot, id, chan)
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_JOIN', bot, chan)
        else:
            yield sign('OTHER_JOIN', bot, id, chan)

@link('PART')
def part(bot, id, chans, msg=None, *args):
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
    yield sign('SOME_KICKED', bot, other_nick, op_id, chan, msg)
    if (other_nick.lower() == bot.nick.lower()):
        yield sign('SELF_KICKED', bot, chan, op_id, msg)
        yield sign('SELF_KICKED_FINAL', bot, chan, op_id, msg)
    else:
        yield sign('OTHER_KICKED', bot, other_nick, op_id, chan, msg)
        yield sign('OTHER_KICKED_FINAL', bot, other_nick, op_id, chan, msg)

@link('QUIT')
def quit(bot, id, msg=None, *args):
    if (id.nick.lower() == bot.nick.lower()):
        yield sign('SELF_QUIT', bot, msg)
    else:
        yield sign('OTHER_QUIT', bot, id, msg)

@link('NICK')
def nick(bot, id, new_nick, *args):
    if id.nick.lower() == bot.nick.lower():
        yield sign('SELF_NICK', bot, new_nick)
        bot.nick = new_nick
    else:
        yield sign('OTHER_NICK', bot, id, new_nick)
    yield sign('SOME_NICK', bot, id, new_nick)

@link('PRIVMSG')
def privmsg(bot, source, target, msg, *args):
    if target.lower() == bot.nick.lower(): target = None
    if isinstance(source, tuple):
        bot.activity = False
        yield sign('MESSAGE', bot, source, target, msg)
        if bot.activity: return
        yield sign('MESSAGE_IGNORED', bot, source, target, msg)
    elif isinstance(source, str):
        yield sign('SMESSAGE', bot, source, target, msg)

@link('NOTICE')
def notice(bot, source, target, msg, *args):
    if target == bot.nick: target = None
    if isinstance(source, tuple):
        yield sign('UNOTICE', bot, source, target, msg)
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

        # NICK: !CMD [ARGS...]
        match = re.match(r'(?P<addr>\S+):\s*!(?P<head>\S*)\s*(?P<body>.*)', msg)
        if match and match.group('addr').lower() == bot.nick.lower(): break

        return
    
    event = '!' + match.group('head').lower()
    body = match.group('body').strip()
    type = 'ACTION_COMMAND' if action else 'COMMAND'
    yield sign(type, bot, id, target, event, body, msg)
    bot.activity = True

    from untwisted.usual import Stop
    raise Stop


@link('HELP*', ('BRIDGE', 'HELP*'))
def h_help_help_short(bot, reply, args):
    reply('help [COMMAND]',
    'Gives detailed information about COMMAND, or lists all commands.')

@link(('HELP', 'help'), ('BRIDGE', 'HELP', 'help'))
def h_help_help(bot, reply, args):
    reply('help [COMMAND]',
    'If COMMAND is given, gives detailed information about its usage;'
    ' otherwise, gives a summary of all available commands.')

@link(('SIMPLE', '!help'), ('SIMPLE', '!commands'), bridge=False)
@link(('BRIDGE', '!help'), ('BRIDGE', '!commands'), bridge=True)
def h_help(bot, name, target, args, reply, bridge):
    lines = []
    callback = lambda *args: lines.append(args)

    def header(str):
        return '\2%s%s\2' % ('!' if bot.conf['bang_cmd'] else '', str)

    if args:
        # Display help for a particular command.
        cmd, args = re.match(r'!?(\S+)\s*(.*)', args).groups()
        cmd = cmd.lower()
        yield sign(('BRIDGE', 'HELP', cmd) if bridge else ('HELP', cmd),
            bot, callback, args)
        if not lines:
            reply('Error: no help is available for "%s".' % cmd, no_bridge=True)
            return
        for line in lines:
            if line[0]: reply(header(line[0]), prefix=False, no_bridge=True)
            for para in line[1:]:
                if para: reply(para, prefix=False, no_bridge=True)

    elif not bridge:
        # Display general help and a summary of all commands.
        reply(
            'Commands are issued by saying%s "%s: !COMMAND",'
            ' where COMMAND is the command and its parameters.'
            ' The following commands are available:'
            % (' "!COMMAND" or' if bot.conf['bang_cmd'] else '', bot.nick),
            prefix=False, no_bridge=True)

        yield sign('HELP*', bot, callback, args)
        lines = map(lambda l: (header(l[0]),) + l[1:], lines)
        for line in util.align_table(lines):
            reply(line, prefix=False, no_bridge=True)

        del lines[:]
        yield sign('HELP', bot, callback, args)
        if lines: reply('Other commands: %s.' % ', '.join(
            '\2%s\2' % l[0].split()[0] for l in lines),
            prefix=False, no_bridge=True)

    else:
        yield sign(('BRIDGE', 'HELP*'), bot, callback, args)
        yield sign(('BRIDGE', 'HELP'), bot, callback, args)
        if lines:
            reply('Available commands: %s.' % ', '.join(
                '\2%s\2' % l[0].split()[0] for l in lines),
                prefix=False, no_bridge=True)
        
