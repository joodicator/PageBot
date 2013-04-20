import socket
import re

import untwisted.utils.common as u_common
import untwisted.event as u_event
import untwisted.network as u_network
import untwisted.utils.std as u_std

import util

conf = util.fdict('conf/minecraft.py')
ab_link = util.LinkSet()
mc_link = util.LinkSet()
server = None
bot = None

@ab_link(('MESSAGE', conf['channel']))
def h_message(bot, id, msg):
    chan = conf['channel']
    if msg.startswith('!'): return
    match = re.match(r'\x01ACTION (?P<msg>.*)', msg)
    if match:
        msg = match.group('msg')
        tell_server('%s: * %s %s' % (chan, id.nick, msg))
    else:
        tell_server('%s: <%s> %s' % (chan, id.nick, msg))

@ab_link(('OTHER_JOIN', conf['channel']))
def h_other_join(bot, id):
    chan = conf['channel']
    tell_server('%s: %s joined the channel.' % (chan, id.nick))

@ab_link(('OTHER_PART', conf['channel']))
def h_other_part(bot, id, msg):
    chan = conf['channel']
    tell_server('%s: %s left the channel' % (chan, id.nick)
        + ((' (%s)' % msg) if msg else '') + '.')

@ab_link(('OTHER_KICKED', conf['channel']))
def h_other_kick(bot, other_nick, op_id, msg):
    chan = conf['channel']
    tell_server('%s: %s was kicked by %s' % (chan, other_nick, op_id.nick)
        + ((' (%s)' % msg) if msg else '') + '.')

@ab_link(('OTHER_QUIT_CHAN', conf['channel'].lower()))
def h_other_quit(bot, id, msg):
    chan = conf['channel']
    tell_server('%s: %s quit the network' % (chan, id.nick)
        + ((' (%s)' % msg) if msg else '') + '.')

@mc_link(u_event.FOUND)
def h_found(server, line):
    s_name = conf['server_name']
    chan = conf['channel']

    match = re.match(r'\d{4}(-\d\d){2} \d\d(:\d\d){2} '
                 r'\[INFO\] (?P<info>.*)', line)
    if not match: return
    line = match.group('info')

    name = None
    p_name = lambda: name

    # Chat
    match = re.match('<(?P<name>\S+)> (?P<msg>.*)', line)
    if match:
        name, msg = match.group('name', 'msg')
        if msg.startswith('!'): return
        return bot.send_msg(chan, '%s: <%s> %s' % (s_name, p_name(), msg))

    # Connect
    match = re.match('(?P<name>\S+)\[[^\]]+\] logged in', line)
    if match:
        name = match.group('name')
        return bot.send_msg(chan, '%s: %s joined the game.' % (s_name, p_name()))

    # Disconnect
    match = re.match('(?P<name>\S+) lost connection', line)
    if match:
        name = match.group('name')
        return bot.send_msg(chan, '%s: %s left the game.' % (s_name, p_name()))

    # Kick
    match = re.match(
        '\[(?P<op>\S+): Kicked (?P<victim>\S+) from the game\]', line)
    if match:
        op, name = match.group('op', 'victim')
        return bot.send_msg(chan, '%s: %s left the game.' % (s_name, p_name()))

    # Ban
    match = re.match(
        '\[(?P<op>\S+): Banned player (?P<victim>\S+)\]', line)
    if match:
        op, name = match.group('op', 'victim')
        return bot.send_msg(chan, '%s: %s left the game.' % (s_name, p_name()))

    # Death
    if is_death_message(line):
        match = re.match(r'(?P<name>\S*)(?P<rest>.*)', line)
        name, rest = match.group('name', 'rest')
        return bot.send_msg(chan, '%s: %s%s' % (s_name, p_name(), rest))

def is_death_message(msg):
    phrases = ('was squashed', 'was pricked', 'was shot', 'was blown up',
               'was doomed', 'was slain', 'was killed', 'was pummeled',
               'was knocked', 'walked into', 'drowned', 'blew up',
               'hit the ground', 'fell off', 'fell out', 'fell from',
               'fell into', 'fell out', 'went up','burned', 'got finished',
               'tried to swim', 'died', 'starved', 'suffocated', 'withered')

    for phrase in phrases:
        if re.match(r'\S+ (%s)' % re.escape(phrase), msg): return True
    return False

def install(new_bot):
    global bot
    bot = new_bot
    init_server()
    ab_link.install(bot)

def uninstall(bot):
    ab_link.uninstall(bot)
    kill_server()

def init_server():
    global server
    kill_server()
    server = socket.socket(conf['server_address_family'], socket.SOCK_STREAM)
    server = u_network.Mac(server)
    u_std.install(server)
    server.link(u_event.DATA, u_common.append)
    server.link(u_event.BUFFER, u_common.shrug, '\n')
    mc_link.install(server)
    server.connect(conf['server_address'])

def kill_server():
    global server
    if server == None: return
    server.destroy()
    server.shutdown(socket.SHUT_RDWR)
    server.close()
    server = None

def tell_server(msg):
    while True:
        head, tail = msg[:100], msg[100:]
        server.dump('say %s%s\n' % (head, '...' if tail else ''))
        if not tail: break
        msg = '...' + tail
