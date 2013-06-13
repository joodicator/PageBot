#!/usr/bin/env python2

import main

import untwisted.network
import untwisted.mode
import untwisted.core
import untwisted.event

import debug
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

def h_chat(w, slot, colour, text):
    if slot == 255:
        print text
    elif slot in w.terraria_protocol.players:
        print '<%s> %s' % (w.terraria_protocol.players[slot], text)
    else:
        print '<%s> %s' % (slot, text)

m = untwisted.mode.Mode()
m.domain = 'm'
terraria_protocol.install(m)
m.link(untwisted.event.CLOSE, h_close)
m.link('CHAT', h_chat)

w = untwisted.network.Work(m, socket.socket())
w.connect(('149.241.77.185', 25565))

terraria_protocol.login(w, 'PageBot%s' % int(time.time()))

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
