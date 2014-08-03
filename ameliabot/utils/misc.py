def send_msg(server, target, msg, **kwds):
    server.dump('PRIVMSG %s :%s\r\n' % (target, msg))
    server.drive('SEND_MSG', server, target, msg, kwds)
    server.activity = True

def send_cmd(server, cmd):
    server.dump('%s\r\n' % cmd)
    server.activity = True
