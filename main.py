#!/usr/bin/python2.7

import sys, os, os.path
os.chdir(os.path.dirname(sys.argv[0]))
sys.path[0:0] = ['.', 'ameliabot', 'page', 'lib']

conf = {
    'server':   'localhost',
    'port':     6667,
    'nick':     'Page',
    'user':     'Page',
    'name':     'Page',
    'channels': ['#page'],
    'plugins':  ['message', 'nickserv', 'control', 'tell']
}
execfile('conf/bot.py', conf)

if '--debug' in sys.argv: conf['plugins'].insert(0, 'debug')

from amelia import AmeliaBot
AmeliaBot(conf).mainloop()
