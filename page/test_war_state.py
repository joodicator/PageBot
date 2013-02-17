#!/usr/bin/env python2

from __future__ import print_function
from war_state import *

game = State()
game.begin()

while True:
    print('\33[2J\33[1;1H', end='')
    game.show_update(print)
    raw_input()
    game.pass_move()
