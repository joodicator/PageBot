from untwisted.event import CLOSE, TICK, FOUND
from untwisted.magic import sign
import socket
import time

__is_local__ = True

last_ping = time.time()
ping_sent = False

def install(poll):
    poll.link('PING', ping)
    poll.link(TICK, tick)
    poll.link('CLOSING', handle_close)
    poll.link(FOUND, found)

def uninstall(poll):
    poll.unlink('PING', ping)
    poll.unlink(TICK, tick)
    poll.unlink('CLOSING', handle_close)
    poll.unlink(FOUND, found)

def ping(bot, prefix, server):
    reply = 'PONG :%s\r\n' % server
    bot.dump(reply)

def found(bot, *args):
    global last_ping
    global ping_sent
    last_ping = time.time()
    ping_sent = False

def tick(bot):
    global ping_sent
    elapsed = time.time() - last_ping
    if elapsed > bot.conf['timeout']/2 and not ping_sent:
        bot.dump('PING :%s\r\n' % bot.nick)
        ping_sent = True
    elif elapsed > bot.conf['timeout']:
        print '! ping timeout: %ss' % elapsed
        yield sign(CLOSE, bot)

def handle_close(bot):
    bot.shutdown(socket.SHUT_RDWR)
    bot.close()
