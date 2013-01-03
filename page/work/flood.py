from collections import namedtuple
from util import LinkSet
import time

LOG_SIZE = 1024

link, install, uninstall = LinkSet().triple()
log_entry = namedtuple('log_entry', ('time', 'user', 'msg'))
channels = dict()

@link('MESSAGE')
@link('NOTICE')
def message(bot, source, target, msg):
    if target == None:
        continue
    if target not in channels:
        channels[target] = Channel()
    channels[target].message(bot, source, msg)


class Channel(object):
    __slots__ = 'log'
    
    def __init__(self):
        self.log = list()
    
    def message(self, bot, user, msg):
        stamp = time.time()
        score = 0
        for ptime, puser, pmsg in self.log:
            
        
        if len(self.log) == LOG_SIZE: self.log.pop(0)
        self.log.append(log_entry(stamp, user, msg))

def similarity(str1, str2):
    ptr1 = ptr2 = 0
    score = 0
    while True:
        if str1[ptr1] == str2[ptr2]:
            ptr1 += 1
            ptr2 += 1
            score += 1
            continue
        ind1 = str1.index(str2[ptr2])
        ind2 = str2.index(str1[ptr1])
        if ind1 < ind2:
            
