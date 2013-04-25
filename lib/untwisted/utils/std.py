from untwisted.network import *
from untwisted.event import *

def install(obj):
    obj.link(READ, update)
    obj.link(WRITE, flush)

def uninstall(obj):
    obj.unlink(READ, update)
    obj.unlink(WRITE, flush)

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
        obj.queue = obj.queue[size:]
        yield sign(DUMPED, obj)
    ##################
