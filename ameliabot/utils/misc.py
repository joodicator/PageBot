def send_msg(server, target, msg):
    server.dump('PRIVMSG %s :%s\r\n' % (target, msg))

def send_cmd(server, cmd):
    server.dump('%s\r\n' % cmd)
