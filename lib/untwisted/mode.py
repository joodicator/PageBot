try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
import traceback
from usual import *

class Mode(object):
    def __init__(self, default=void):
        """ Constructor for Mode """

        self.base = OrderedDict()
        self.default = default
    
    def drive(self, event, *args):
        """ It evaluates all callbacks linked to event """

        for signal, handle in self.base.keys():
            ################
            if signal == event:
                try:
                    old_args = self.base[signal, handle] 
                except KeyError:
                    continue
                new_args = glue(args, old_args)

                try:
                    #it evaluates handle
                    seq = handle(*new_args)

                    if seq:
                        chain(self, seq)        
                except Exception as excpt:
                    #it stops processing event
                    if isinstance(excpt, Stop):
                        break
                    elif isinstance(excpt, Kill):
                        raise
                    else:
                        traceback.print_exc()

             ################

        self.default(event, *args)

    def link(self, event, callback, *args):
        """ This function maps an event to a callback. """

        self.base[event, callback] = args

    def unlink(self, event, callback, *args):
        """ This function unmap an event to a callback. """

        del self.base[event, callback]
