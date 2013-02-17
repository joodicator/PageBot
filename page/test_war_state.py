#!/usr/bin/env python2

from war_state import *

game = State()
game.begin()

posn = 0
def reply(str):
    global posn
    posn += 1
    print str

while True:
    game.show_update(reply)
    game.pass_move()
    raw_input()
    print '\33[%sA' % (posn + 2)
    posn = 0
