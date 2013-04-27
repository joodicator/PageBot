#!/usr/bin/env python2

import sys, os, os.path
os.chdir(os.path.dirname(sys.argv[0]))
sys.path[0:0] = ['.', 'ameliabot', 'page', 'lib']

conf = {
    'server':   'localhost',
    'port':     6667,
    'nick':     'Page',
    'user':     'Page',
    'name':     'https://github.com/JosephCrowe/page-ircbot',
    'channels': ['#page'],
    'plugins':  ['runtime', 'message', 'nickserv', 'auth', 'control',
                 'channel', 'tell']
}
execfile('conf/bot.py', conf)

if '--debug' in sys.argv: conf['plugins'].insert(0, 'debug')


import amelia
from untwisted.event import CLOSE

bot = amelia.AmeliaBot(conf)
bot.domain = 'bot'
try:
    bot.mainloop()
except BaseException as e:
    bot.drive('EXCEPTION', bot, e)
    bot.mainloop()
