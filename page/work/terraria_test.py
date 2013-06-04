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

m = untwisted.mode.Mode()
m.domain = 'm'
terraria_protocol.install(m, debug=True)
m.link(untwisted.event.CLOSE, h_close)

w = untwisted.network.Work(m, socket.socket())
w.connect(('vaylon', 7777))

terraria_protocol.login(w, 'PageBot%s' % time.clock())

while True:
    try:
        untwisted.core.gear.mainloop()
    except KeyboardInterrupt:
        try:
            exec raw_input()
        except KeyboardInterrupt:
            h_close(w)
        except:
            traceback.print_exc()
