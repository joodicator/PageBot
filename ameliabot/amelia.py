from importlib import import_module
from socket import *
import sys
import re

from plugins.standard import head
from untwisted.core import gear
from untwisted.network import Mac
from untwisted.event import CLOSE
from untwisted.usual import Kill
import utils.misc
import stdlog as std
import xirclib

RPL_WELCOME         = '001'
RPL_ISUPPORT        = '005'
ERR_NICKNAMEINUSE   = '433'

default_conf = {
    'server':       'irc.freenode.net',
    'port':         6667,
    'nick':         'ameliabot',
    'user':         'ameliabot',
    'name':         'ameliabot',
    'host':         '0',
    'channels':     ['#untwisted'],
    'plugins':      [],
    'timeout':      180, # 180s = 3m
    'bang_cmd':     True
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
        Mac.__init__(self, sock, is_read=True, is_write=True)
        if 'bind_addr' in self.conf: sock.bind(self.conf['bind_addr'])
        address = gethostbyname(self.conf['server'])
        sock.setblocking(0)
        sock.connect_ex((address, self.conf['port']))

        # Initialise miscellaneous attributes
        self.isupport = {
            'PREFIX':    ('ohv','@%+'),
            'CHANMODES': ('be','k','l','') }

        # Initialise events
        std.install(self)
        xirclib.install(self)
        self.link(ERR_NICKNAMEINUSE,    self.h_err_nicknameinuse)
        self.link(RPL_WELCOME,          self.h_rpl_welcome)
        self.link(RPL_ISUPPORT,         self.h_rpl_isupport)
        
        # Load plugins
        self.conf['plugins'][:0] = ['plugins.standard.head']
        self.load_plugins()

        # Start registration
        self.nick = self.conf['nick']
        self.send_cmd('NICK %s' % self.nick)
        self.send_cmd('USER %(user)s %(host)s %(server)s :%(name)s' % self.conf) 

    def load_plugins(self):
        loaded_plugins = []
        def load_plugin(name, level):
            plugin = import_module(name)
            if plugin in loaded_plugins: return

            loaded_plugins.append(plugin)
            arrow = ' ' + level*'--' + '>' if level else ''
            print '! plugin:%s %s' % (arrow, name)

            if hasattr(plugin, '__depends__'):
                for dep_name in plugin.__depends__:
                    load_plugin(dep_name, level+1)

        for name in self.conf['plugins']:
            load_plugin(name, 0)

        for plugin in loaded_plugins:
            plugin.install(self)

    def h_err_nicknameinuse(self, bot, *args):
        self.nick += "_"
        self.send_cmd('NICK %s' % self.nick)

    def h_rpl_isupport(self, bot, pre, target, *args):
        for arg in args[:-1]:
            match = re.match(r'-?(?P<key>[^=]+)(=(?P<val>.*))?', arg)
            key, val = match.group('key', 'val')
            if key == 'PREFIX' and val:
                match = re.match(r'(\((?P<ms>[^)]*)\))?(?P<ps>.*)', val)
                val = match.group('ms', 'ps')
            elif key == 'CHANMODES' and val:
                val = tuple(val.split(','))
            bot.isupport[key] = val

    def h_rpl_welcome(self, *args):
        for channel in self.conf['channels']:
            self.send_cmd('JOIN %s' % channel)
        self.drive('AUTOJOIN', self)

    def mainloop(self):
        return gear.mainloop()

if __name__ == '__main__':
    gear = AmeliaBot()
    gear.mainloop()

