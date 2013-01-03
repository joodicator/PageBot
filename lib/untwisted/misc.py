def xmap(obj, event, callback, *args):
    obj.link(event, callback, *args)

def ymap(obj, event, callback):
    obj.unlink(event, callback)

def spawn(obj, event, *args):
    obj.drive(event, *args)

