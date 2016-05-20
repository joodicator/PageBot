from importlib import import_module
from itertools import *
from socket import *
import time
import sys
import re

from plugins.standard import head
from untwisted.core import gear
from untwisted.network import Mac
from untwisted.event import CLOSE, TICK
from untwisted.usual import Kill
import stdlog as std
import xirclib

RPL_WELCOME         = '001'
RPL_ISUPPORT        = '005'
ERR_NICKNAMEINUSE   = '433'

class NotInstalled(Exception): pass
class AlreadyInstalled(Exception): pass

default_conf = {
    'server':        'irc.freenode.net',
    'port':          6667,
    'nick':          'ameliabot',
    'user':          'ameliabot',
    'name':          'ameliabot',
    'host':          '0',
    'channels':      ['#untwisted'],
    'plugins':       [],
    'timeout':       180, # 180s = 3m
    'bang_cmd':      True,
    'flood_limits':  [(40,20), (0.5,1)]
}

class AmeliaBot(Mac):
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

        # Initialise flood-protection system
        self.send_times = []
        self.flood_buffer = []
        self.flood_active = False

        # Initialise events
        std.install(self)
        xirclib.install(self)
        self.link(ERR_NICKNAMEINUSE,    self.h_err_nicknameinuse)
        self.link(RPL_WELCOME,          self.h_rpl_welcome)
        self.link(RPL_ISUPPORT,         self.h_rpl_isupport)
        self.link(TICK,                 self.h_tick)
        self.link('PRE_AUTOJOIN',       self.h_pre_autojoin)
        
        # Load plugins
        self.conf['plugins'][:0] = ['plugins.standard.head']
        self.load_plugins()

        # Start registration
        self.nick = self.conf['nick']
        self.send_cmd('NICK %s' % self.nick)
        self.send_cmd('USER %(user)s %(host)s %(server)s :%(name)s' % self.conf) 

    def load_plugins(self):
        loaded_plugins = []
        for name in self.conf['plugins']:
            plugin = import_module(name)
            loaded_plugins.append(plugin)

        for plugin in loaded_plugins:
            try:
                plugin.install(self)
            except AlreadyInstalled:
                pass

    def h_err_nicknameinuse(self, bot, *args):
        self.nick += "_"
        self.send_cmd('NICK %s' % self.nick)

        if hasattr(self, 'auto_nick'):
            self.auto_nick = self.nick
        else:
            self.auto_nick = self.nick
            self.drive('AUTONICK', self)

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
        self.unlink(ERR_NICKNAMEINUSE, self.h_err_nicknameinuse)
        self.drive('PRE_AUTOJOIN', self)

    def h_pre_autojoin(self, *args):
        for channel in self.conf['channels']:
            self.send_cmd('JOIN %s' % channel)
        self.drive('AUTOJOIN', self)

    def mainloop(self):
        return gear.mainloop()

    def send_msg(self, target, msg, **kwds):
        self.send_line('PRIVMSG %s :%s' % (target, msg), **kwds)
        self.activity = True
    
    def send_cmd(self, cmd, **kwds):
        self.send_line(cmd, **kwds)
        self.activity = True

    def send_line(self, line, defer=False, **kwds):
        flood_limits = self.conf['flood_limits']
        now = time.time()
        cut = now - max(s for (s,l) in flood_limits)
        while self.send_times and self.send_times[0] < cut:
            del self.send_times[0]

        for flood_seconds, flood_lines in flood_limits:
            cut = now - flood_seconds
            times = dropwhile(lambda t: t < cut, self.send_times)
            if len(list(times)) >= flood_lines:
                self.flood_active = True
                break

        if defer or self.flood_active:
            self.flood_buffer.append((line, kwds))
        else:
            self.send_times.append(now)
            line = line[:510]
            self.dump('%s\r\n' % line)
            match = re.match(r'PRIVMSG (?P<target>\S+) :(?P<msg>.*)', line)
            if match: self.drive('SEND_MSG',
                self, match.group('target'), match.group('msg'), kwds)

    def h_tick(self, bot):
        if not self.flood_active: return
        lines = self.flood_buffer
        self.flood_buffer = []
        self.flood_active = False
        for line, kwds in lines:
            self.send_line(line, **kwds)

if __name__ == '__main__':
    gear = AmeliaBot()
    gear.mainloop()

