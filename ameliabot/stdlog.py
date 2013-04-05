from untwisted.network import *
from untwisted.event import *
import time

def install(obj):
    obj.link(READ, update)
    obj.link(WRITE, flush)

def update(obj):
    if obj.server:
        yield sign(ACCEPT, obj)
        return

    try:
        obj.data = obj.recv(obj.SIZE)
    except Exception as excpt:
        yield sign(RECV_ERR, obj, excpt)
        return
    ################
    ilog(obj.data)
    if not obj.data:
        yield sign(CLOSE, obj)
    else:
        yield sign(LOAD, obj)

        yield sign(DATA, obj)

def flush(obj):
    if obj.queue:
        data = obj.queue[:obj.BLOCK]
        try:
            size = obj.send(data)
        except Exception as excpt:
            yield sign(SEND_ERR, obj, excpt)
            return
        olog(obj.queue[:size])
        obj.queue = obj.queue[size:]
        yield sign(DUMPED, obj)
    ##################

ibuf = ''
obuf = ''
TERM = '\r\n'

def ilog(data):
    global ibuf
    ibuf += data
    ibuf = ibuf.split(TERM)
    for line in ibuf[:-1]:
        print '%s > %s' % (time.strftime('%H:%M:%S'), line)
    ibuf = ibuf[-1]
    
def olog(data):
    global obuf
    obuf += data
    obuf = obuf.split(TERM)
    for line in obuf[:-1]:
        print '%s < %s' % (time.strftime('%H:%M:%S'), line)
    obuf = obuf[-1]
