import socket

import untwisted.utils.common as u_common
import untwisted.event as u_event
import untwisted.network as u_network
import untwisted.utils.std as u_std

import util
import debug

conf = util.fdict('conf/minecraft.py')
ab_link = util.LinkSet()
mc_link = util.LinkSet()
server = None
bot = None

@ab_link(('MESSAGE', conf['channel']))
def h_message(bot, id, msg):
    server.dump('say <%s:%s> %s\n' % (conf['channel'], id.nick, msg))

@mc_link(u_event.FOUND)
def h_found(server, line):
    bot.send_msg(conf['channel'], line)

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
