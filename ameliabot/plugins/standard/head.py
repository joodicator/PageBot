from untwisted.event import BUFFER, CLOSE

def install(poll):
    poll.link('PING', pong)
    poll.link(CLOSE, handle_close)
    pass

def pong(work, prefix, server):
    reply = 'PONG :%s\r\n' % server
    work.dump(reply)

def handle_close(server):
    server.close()
    server.destroy()
