from untwisted.magic import sign
from util import LinkSet, ID
import re

link, install, uninstall = LinkSet().triple()

@link('JOIN')
def join(bot, source, chans, *args):
    id = ID(*source)
    for chan in chans.split(','):
        if (id.nick.lower() == bot.nick.lower()):
            yield sign('SELF_JOIN', bot, chan)
            yield sign(('SELF_JOIN', chan), bot)
        else:
            yield sign('OTHER_JOIN', bot, id, chan)
            yield sign(('OTHER_JOIN', chan), bot, id)

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
    yield sign(event, bot, id, target, match.group('body'), msg)
    yield sign((event, target), bot, id, match.group('body'), msg)


@link('COMMAND_LIST')
def list_help(bot, reply):
    reply('help OR commands', 'Shows this list.')

@link('!help')
@link('!commands')
def help(bot, id, target, args, full_msg):
    reply = lambda msg: bot.send_msg(target or id.nick, msg)
    reply(
        'Commands are issued by saying "!COMMAND" or "%s: COMMAND" or, by PM,'
        ' just "COMMAND". The following commands are available:' % bot.nick)
    def command_list(head=None, body=None):
        if head: reply(head)
        if body: reply('    ' + body)
    yield sign('COMMAND_LIST', bot, command_list)
