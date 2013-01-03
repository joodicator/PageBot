from importlib import import_module
from socket import *
import sys

from plugins.standard import head
from untwisted.core import gear
from untwisted.network import Mac
import utils.misc
import stdlog as std
import xirclib

default_conf = {
    'server':   'irc.freenode.net',
    'port':     6667,
    'nick':     'ameliabot',
    'user':     'ameliabot',
    'name':     'ameliabot',
    'host':     '0',
    'channels': ['#untwisted'],
    'plugins':  []
}

class AmeliaBot(Mac):
    send_cmd = utils.misc.send_cmd
    send_msg = utils.misc.send_msg

    def __init__(self, conf=None):
        # Load configuration
        self.conf = default_conf.copy()
        if conf: self.conf.update(conf)
        
        # Initialise socket
        sock = socket(AF_INET, SOCK_STREAM)
        address = gethostbyname(self.conf['server'])
        sock.connect((address, self.conf['port']))
        Mac.__init__(self, sock)
        
        # Initialise events
        std.install(self)
        xirclib.install(self)
        self.link('433', self.err_nicknameinuse)
        self.link('001', self.registered)
        
        # Load plugins
        def plugins():
            yield head
            for name in self.conf['plugins']:
                print '! plugin: %s' % name
                yield import_module(name)
        for plugin in plugins():
            plugin.install(self)
        
        # Start registration
        self.nick = self.conf['nick']
        self.send_cmd('NICK %s' % self.nick)
        self.send_cmd('USER %(user)s %(host)s %(server)s :%(name)s' % self.conf) 
    
    def err_nicknameinuse(self, bot, *args):
        self.nick += "_"
        self.send_cmd('NICK %s' % self.nick)

    def registered(self, *args):
        for channel in self.conf['channels']:
            self.send_cmd('JOIN %s' % channel)

    def mainloop(self):
        return gear.mainloop()

if __name__ == '__main__':
    gear = AmeliaBot()
    gear.mainloop()

