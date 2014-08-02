try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import traceback
from usual import *

class Mode(object):
    def __init__(self, default=void):
        # Constructor for Mode

        self.base = OrderedDict()
        self.default = default
    
    def drive(self, event, *args):
        # It evaluates all callbacks linked to event

        for signal, handle in self.base.keys():
            ################
            if signal == event:
                try:
                    old_args, kwds = self.base[signal, handle] 
                except KeyError:
                    continue
                new_args = glue(args, old_args)

                try:
                    #it evaluates handle
                    seq = handle(*new_args, **kwds)

                    if seq:
                        chain(self, seq)
                except Stop:
                    break
                except Exception:
                    traceback.print_exc()
                except Kill:
                    raise

             ################

        self.default(event, *args)

    def link(self, event, callback, *args, **kwds):
        # This function maps an event to a callback.

        self.base[event, callback] = (args, kwds)

    def unlink(self, event, callback, *args, **kwds):
        # This function unmap an event to a callback.

        del self.base[event, callback]
