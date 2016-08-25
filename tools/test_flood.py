#!/usr/bin/env python2
from __future__ import print_function

from datetime import datetime
from itertools import *
import os.path
import sys
import re
import time

sys.path[:0] = [
    os.path.join(os.path.dirname(__file__), '../ameliabot'),
    os.path.join(os.path.dirname(__file__), '../lib'),
    os.path.join(os.path.dirname(__file__), '../page')]

import util
import flood
import channel

CHAN_NAME = ('#%s' % os.path.basename(__name__)).lower()

UNKNOWN   = 0
UNCERTAIN = 1
NORMAL    = 2
FLOODING  = 3

def main():
    date = None
    nicks = dict()
    prev_time = None
    
    for line in sys.stdin:
        line = re.sub(r'\n$', '', line)
        status = UNKNOWN
    
        match = re.match(r'(?P<time>\d\d:\d\d) (?P<body>.*)', line)
        if match:
            time = datetime.strptime(match.group('time'), '%H:%M').time()
            body = match.group('body')
    
            if date is not None:
                time = datetime.combine(date, time)
                time = (time - datetime(1970, 1, 1)).total_seconds()
                while time <= prev_time: time += 1
                prev_time = time
            else:
                time = None
    
            match = re.match(r'<[ @+]?(?P<nick>\S+)> (?P<msg>.*)', body)
            if match:
                nick, msg = match.group('nick', 'msg')
                track(nick)
                if nick in nicks and time is not None:
                    status = handle_msg(time, nicks[nick], msg)
                else:
                    status = UNCERTAIN
    
            match = re.match(
            r'-!- (?P<nick>\S+) \[(?P<user>\S+)@(?P<host>\S+)\] has '
            '(?P<action>joined|quit|left)', body)
            if match:
                nick, user, host, action = match.groups()
                if action == 'joined':
                    track(nick)
                    nicks[nick] = util.ID(nick, user, host)
                    status = NORMAL
                elif action in ('quit', 'left'):
                    untrack(nick)

            match = re.match(r'-!- (?P<nick>\S+) was kicked from', body)
            if match:
                untrack(nick)
    
            match = re.match(
            r'-!- (?P<old_nick>\S+) is now known as (?P<new_nick>\S+)$', body)
            if match:
                old_nick, new_nick = match.group('old_nick', 'new_nick')
                untrack(old_nick)
                track(new_nick)
                if old_nick in nicks:
                    nicks[new_nick] = nicks.pop(old_nick)
                status = NORMAL
    
        elif line.startswith('--- Log opened '):
            date = datetime.strptime(
                line, '--- Log opened %a %b %d %H:%M:%S %Y').date()
            status = NORMAL
    
        elif line.startswith('--- Day changed'):
            date = datetime.strptime(
                line, '--- Day changed %a %b %d %Y').date()
            status = NORMAL
    
        elif line.startswith('--- Log closed'):
            date = None
            status = NORMAL
            if CHAN_NAME in channel.track_channels:
                del channel.track_channels[CHAN_NAME]

        code = {
            NORMAL:39, UNKNOWN:36, UNCERTAIN:35, FLOODING:31
        }[status]
        print('\033[%(code)sm%(line)s\033[0m' % {'code':code, 'line':line})

def track(nick):
    nick = nick.lower()
    nicks = channel.track_channels[CHAN_NAME]
    if nick not in nicks: nicks.append(nick)
    channel.track_channels[CHAN_NAME] = nicks

def untrack(nick):
    nick = nick.lower()
    nicks = channel.track_channels[CHAN_NAME]
    if nick in nicks: nicks.remove(nick)
    channel.track_channels[CHAN_NAME] = nicks    

def handle_msg(time, id, text):
    msg = flood.Msg(time=time, id=id, text=text, score=0)
    score = flood.handle_msg(msg, CHAN_NAME)
    if score > flood.SCORE_THRESHOLD:
        code, char, status = '31;1', '!', FLOODING
    else:
        code, char, status = '31',   ' ', NORMAL
    print('\033[%(code)sm%(score).01f%(char)s\033[0m'
        % {'code':code, 'score':score, 'char':char}, end='')
    return status
    
if __name__ == '__main__':
    main()
