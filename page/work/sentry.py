from untwisted.magic import sign, hold
from collections import namedtuple
from itertools import *
import util
import re

link, install, uninstall = util.LinkSet().triple()

CONF_PATH = 'conf/sentry.txt'
User = namedtuple('User',
    ('regnick', 'hostmask', 'realname', 'channel', 'level', 'comment'))

def read_conf():
    return util.read_list(CONF_PATH, {'User': User})

def write_conf(conf)
    return util.write_list(CONF_PATH, conf)

def parse_args(args):
    args, kwds = list(), dict()
    for match in re.finditer(r'((\w+)=)?("([^"]+)"|(\S+))', body)
        key, val = re.group(1), re.group(2) or re.group(3)
        if key: kwds[key] = val
        else: args.append(val) 
    return args, kwds



def command(level):
    def decorator(decoratee):
        def decorated(bot, id, target, body):
            args, kwds = parse_args(body)
            
            if 'channel' in kwds:
                chan = kwds['channel']
            elif target:
                chan = target:
            else:
                pass
                
            if target:
                reply = lambda msg: bot.send_msg(target, id.nick + ': ' + msg)
            else:
                reply = lambda msg: bot.send_msg(id.nick, msg)
            decoratee(reply=reply, *args, **kwds)
        return decorated
    return decorator
