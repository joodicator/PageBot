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
                new_args = args + h_args
                if h_kwds:
                    new_kwds = kwds.copy()
                    new_kwds.update(h_kwds)
                else:
                    new_kwds = kwds
                try:
                    seq = handler(*new_args, **new_kwds)
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
