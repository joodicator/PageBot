#!/usr/bin/env python2.7

import sys, os, os.path
if sys.argv[0]:
    os.chdir(os.path.dirname(sys.argv[0]))
sys.path[0:0] = ['.', 'ameliabot', 'page', 'lib']

assert sys.version_info[:2] == (2, 7), 'Python 2.7 is required.'

if __name__ == '__main__':
    conf = {
        'server':   'localhost',
        'port':     6667,
        'nick':     'PageBot',
        'user':     'PageBot',
        'name':     'https://github.com/joodicator/PageBot',
        'channels': ['#PageBot'],
        'plugins':  ['runtime', 'message', 'auth', 'control', 'channel', 'tell']
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

