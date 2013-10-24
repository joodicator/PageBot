#!/usr/bin/env python2

import main

import untwisted.network
import untwisted.mode
import untwisted.core
import untwisted.event

import debug
import runtime
import terraria_protocol

import sys
import socket
import traceback
import time

def h_close(w):
    w.destroy()
    w.shutdown(socket.SHUT_RDWR)
    w.close()
    sys.exit()

m = untwisted.mode.Mode()
m.domain = 'm'
runtime.install(m)
terraria_protocol.install(m, debug=('--debug' in sys.argv))
m.link(untwisted.event.CLOSE, h_close)

def h_chat(w, slot, colour, text):
    if slot == 255:
        print text
    elif slot in w.terraria_protocol.players:
        print '<%s> %s' % (w.terraria_protocol.players[slot], text)
    else:
        print '<%s> %s' % (slot, text)
m.link('CHAT', h_chat)

w = untwisted.network.Work(m, socket.socket())
w.connect(('50.130.76.238', 7777))

terraria_protocol.login(w, 'TestBot', 'fto', version='Terraria71')

while True:
    try:
        untwisted.core.gear.mainloop()
    except KeyboardInterrupt:
        try:
            terraria_protocol.chat(w, raw_input())
        except KeyboardInterrupt:
            h_close(w)
    except:
        traceback.print_exc()
        h_close(w)
