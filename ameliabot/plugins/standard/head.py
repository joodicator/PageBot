from untwisted.event import CLOSE, TICK
from untwisted.magic import sign
import time

last_ping = time.time()

def install(poll):
    poll.link('PING', pong)
    poll.link(TICK, tick)
    poll.link(CLOSE, handle_close)

def pong(bot, prefix, server):
    global last_ping
    last_ping = time.time()
    reply = 'PONG :%s\r\n' % server
    bot.dump(reply)

def tick(bot):
    elapsed = time.time() - last_ping
    if elapsed > bot.conf['timeout']:
        print '! ping timeout: %ss' % elapsed
        yield sign(CLOSE, bot)

def handle_close(bot):
    bot.close()
    bot.destroy()
