#!/usr/bin/env python2

from __future__ import print_function

from datetime import datetime
import sys
import re
import time
import cProfile

import main
import util
import flood

UNKNOWN   = 0
UNCERTAIN = 1
NORMAL    = 2
FLOODING  = 3

def main():
    date = None
    nicks = dict()
    
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
            else:
                time = None
    
            match = re.match(r'<[ @+]?(?P<nick>\S+)> (?P<msg>.*)', body)
            if match:
                nick, msg = match.group('nick', 'msg')
                if nick in nicks and time is not None:
                    handle_msg(time, nicks[nick], msg)
                    status = NORMAL
                else:
                    status = UNCERTAIN
    
            match = re.match(
            r'-!- (?P<nick>\S+) \[(?P<user>\S+)@(?P<host>\S+)\] has joined', body)
            if match:
                nicks[match.group('nick')] = util.ID(**match.groupdict())
                status = NORMAL
    
            match = re.match(
            r'-!- (?P<old_nick>\S+) is now known as (?P<new_nick>\S+)$', body)
            if match:
                old_nick, new_nick = match.group('old_nick', 'new_nick')
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

        code = { NORMAL:39, UNKNOWN:36, UNCERTAIN:35, FLOODING:31 }[status]
        print('\033[%(code)dm%(line)s\033[0m' % {'code':code, 'line':line})

def handle_msg(time, id, text):
    msg = flood.Msg(time=time, id=id, text=text)
    score = flood.handle_msg(msg, id, '#test_flood.py')
    code, char = ('31;1', '!') if score > flood.SCORE_THRESHOLD \
            else ('31', ' ')
    print('\033[%(code)sm%(score).01f%(char)s\033[0m'
        % {'code':code, 'score':score, 'char':char}, end='')
    
if __name__ == '__main__':
    main()
