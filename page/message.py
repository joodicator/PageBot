from untwisted.magic import sign
from util import LinkSet, ID
import util
from itertools import *
import re

link, install, uninstall = LinkSet().triple()

# Reply (in the same channel or by PM, as appropriate) to a message by `id'
# sent to `target' with the message `msg', possibly prefixing the message with
# their nick, unless `prefix' is given as False.
def reply(bot, id, target, msg, prefix=True):
    if prefix and target != None:
        msg = '%s: %s' % (id.nick, msg)
    bot.send_msg(target or id.nick, msg)


@link('JOIN')
def join(bot, source, chans, *args):
    id = ID(*source)
    for chan in chans.split(','):
        yield sign('SOME_JOIN', bot, id, chan)
        yield sign(('SOME_JOIN', chan), bot, id)
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_JOIN', bot, chan)
            yield sign(('SELF_JOIN', chan), bot)
        else:
            yield sign('OTHER_JOIN', bot, id, chan)
            yield sign(('OTHER_JOIN', chan), bot, id)

@link('PART')
def part(bot, source, chans, msg=None, *args):
    id = ID(*source)
    for chan in chans.split(','):
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_PART', bot, chan, msg)
            yield sign(('SELF_PART', chan), bot, msg)
        else:
            yield sign('OTHER_PART', bot, id, chan, msg)
            yield sign(('OTHER_PART', chan), bot, id, msg)

@link('KICK')
def kicked(bot, op_id, chan, other_nick, msg=None, *args):
    op_id = ID(*op_id)
    if (other_nick.lower() == bot.nick.lower()):
        yield sign('SELF_KICKED', bot, chan, op_id, msg)
        yield sign(('SELF_KICKED', chan), bot, op_id, msg)
    else:
        yield sign('OTHER_KICKED', bot, other_nick, op_id, chan, msg)
        yield sign(('OTHER_KICKED', chan), bot, other_nick, op_id, msg)

@link('QUIT')
def quit(bot, source, msg=None, *args):
    id = ID(*source)
    if (id.nick.lower() == bot.nick.lower()):
        yield sign('SELF_QUIT', bot, msg)
    else:
        yield sign('OTHER_QUIT', bot, id, msg)

@link('PRIVMSG')
def privmsg(bot, source, target, msg, *args):
    if target == bot.nick: target = None
    if type(source) == tuple:
        id = ID(*source)
        yield sign('MESSAGE', bot, id, target, msg)
        yield sign(('MESSAGE', target), bot, id, msg)
    elif type(source) == str:
        yield sign('SMESSAGE', bot, source, target, msg)
        yield sign(('SMESSAGE', target), bot, source, msg)

@link('NOTICE')
def notice(bot, source, target, msg, *args):
    if target == bot.nick: target = None
    if type(source) == tuple:
        id = ID(*source)
        yield sign('UNOTICE', bot, id, target, msg)
        yield sign(('UNOTICE', target), bot, id, msg)
    elif type(source) == str:
        yield sign('SNOTICE', bot, source, target, msg)
        yield sign(('SNOTICE', target), bot, source, msg)

@link('MESSAGE')
def message(bot, id, target, msg):
    while True:
        # !CMD [ARGS...]
        match = re.match(r'!(?P<head>\S+)\s*(?P<body>.*)', msg)
        if match: break
        # NICK: CMD [ARGS...]
        match = re.match(r'(?P<addr>\S+):\s+(?P<head>\S+)\s*(?P<body>.*)', msg)
        if match and match.group('addr').lower() == bot.nick.lower(): break
        # (Private) CMD [ARGS...]
        match = re.match(r'\s*(?P<head>\S+)\s*(?P<body>.*)', msg)
        if match and target == None: break
        return
    event = '!' + match.group('head').lower()
    body = match.group('body').strip()
    yield sign(event, bot, id, target, body, msg)
    yield sign((event, target), bot, id, body, msg)


@link('HELP')
@link(('HELP', 'help'))
@link(('HELP', 'commands'))
def h_help_help(bot, reply, args):
    reply('help',           'Shows a summary of all available commands.')
    reply('help COMMAND',   'Gives detailed information about COMMAND.')
    reply('commands',       'A synonym for "help".')

@link('!help')
@link('!commands')
def h_help(bot, id, target, args, full_msg):
    lines = []
    callback = lambda *args: lines.append(args)
    output = lambda msg: bot.send_msg(target or id.nick, msg)

    if args:
        # Display help for a particular command.
        cmd, args = re.match(r'(\S+)\s*(.*)', args).groups()
        yield sign(('HELP', cmd.lower()), bot, callback, args)
        if not lines:
            reply(bot, id, target,
                'Error: no help is available for "%s".' % cmd)
            return
        for line in lines:
            if line[0]: output('\2' + line[0] + '\2')
            for para in line[1:]:
                if para: output('    ' + para)
    else:
        # Display general help and a summary of all commands.
        output(
            'Commands are issued by saying "!COMMAND" or "%s: COMMAND" or,'
            ' by PM, just "COMMAND", where COMMAND is the command and its'
            ' parameters. The following commands are available:' % bot.nick)
        yield sign('HELP', bot, callback, args)
        lines = map(lambda l: ('\2' + l[0] + '\2',) + l[1:], lines)
        map(output, util.align_table(lines))
