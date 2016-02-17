import UserDict

import traceback

void = lambda *args, **kwds: None

def chain(poll, seq):
    try:
        for ind in seq:
            ind(poll, seq)
    except StopIteration:
        pass

def apply(handle, *args, **kwargs):
    try:
        seq = handle(*args, **kwargs)
        return seq
    except:
        traceback.print_exc()

def mix(*args):
    total = dict()
    for ind in args:
        total.update(ind)
    return total

def glue(*args):
    total = tuple()
    for ind in args:
        total = total + ind
    return total

def arg(*args, **kwargs):
    return (args, kwargs)

class Stop(Exception):
    pass

class Kill(Exception):
    pass
