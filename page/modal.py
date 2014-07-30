#===============================================================================
# modal.py - allows certain types of input to be multiplexed between different
# modules, depending on which "mode" is active in each channel.
#
# A module wishing to take control of the channel may call set_mode(chan,M) to
# enter the mode M, which must be unique to that module; then call
# set_mode(chan,M) again after each soft or hard reload if it wishes to retain
# the mode; then clear_mode() when control is to be released.

import inspect
from untwisted.magic import sign
import util

chan_mode = dict()

#-------------------------------------------------------------------------------
# Request for the given mode to be established in the given channel. If there is
# no current mode, the request is successful, and None is returned; otherwise,
# the request fails, and the existing mode is returned.
#
# When 'CONTEND_MODE' is raised with the arguments (bot, id, target), the module
# holding the current mode should indicate to the user what activity is holding
# the mode, and possibly how it can be released.
def set_mode(chan, mode):
    existing_mode = get_mode(chan)
    if not existing_mode: chan_mode[chan.lower()] = mode
    return existing_mode

#-------------------------------------------------------------------------------
# Clear any mode set for the given channel.
def clear_mode(chan):
    chan = chan.lower()
    if chan in chan_mode: del chan_mode[chan]

#-------------------------------------------------------------------------------
# Return the mode active in the given channel, or None.
def get_mode(chan):
    return chan_mode.get(chan.lower())

#-------------------------------------------------------------------------------
# An event handler decorated with @when_mode(M) (beneath any @link decorators)
# will only be called when the channel given by the handler's "chan" or "target"
# argument has the mode M currently established.
def when_mode(mode):
    def when_mode_dec(fun):
        def when_mode_fun(*args, **kwds):
            cargs = inspect.getcallargs(fun, *args, **kwds)
            chan = cargs.get('chan') or cargs.get('target')
            if get_mode(chan) != mode: return
            yield util.sub(fun(*args, **kwds))
        return when_mode_fun
    return when_mode_dec
