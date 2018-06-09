from itertools import chain
from collections import OrderedDict
import traceback

from usual import *

class Mode(object):
    def __init__(self, default=void):
        # Constructor for Mode

        self._base = dict()
        self.default = default

    def drive(self, event, *args, **kwds):
        # It evaluates all callbacks linked to event
        handlers = self._base.get(event)
        if handlers:
            for handler, (h_args, h_kwds) in handlers.items():
                if kwds:
                    h_kwds = h_kwds.copy()
                    h_kwds.update(kwds)
                try:
                    seq = handler(*(h_args + args), **h_kwds)
                    if seq: chain(self, seq)
                except Stop:
                    break
                except Kill:
                    raise
                except Exception:
                    traceback.print_exc()
        self.default(event, *args, **kwds)

    def link(self, event, callback, *args, **kwds):
        # This function maps an event to a callback.
        callbacks = self._base.get(event)
        if callbacks is None:
            callbacks = OrderedDict()
            self._base[event] = callbacks
        callbacks[callback] = (args, kwds)

    def unlink(self, event, callback, *args, **kwds):
        # This function unmap an event to a callback.
        callbacks = self._base[event]
        del callbacks[callback]
        if not callbacks:
            del self._base[event]
