#===============================================================================
# upoopia.py - an IRC implementation of http://www.unicorn7.org/games/game/553

__depends__ = 'chan_link',

from untwisted.magic import sign

from message import reply
import util
import modal

link, install, uninstall = util.LinkSet().triple()

chans = set()

#-------------------------------------------------------------------------------
def reload(prev):
    if not hasattr(prev, 'chans'): return
    if type(prev.chans) is not set: return
    chans.update(prev.chans)
    for chan in chans: modal.set_mode(chan, 'upoopia')

#-------------------------------------------------------------------------------
@link('!upoopia')
def h_upoopia(bot, id, target, args, full_msg):
    if not target: return
    if modal.get_mode(target):
        yield sign('CONTEND_MODE', bot, id, target)
        return
    modal.set_mode(target, 'upoopia')
    chans.add(target.lower())
    reply(bot, id, target, 'Upoopia started.')

#-------------------------------------------------------------------------------
@link('!')
@modal.when_mode('upoopia')
def h_bang(bot, id, target, args, full_msg):
    reply(bot, id, target, 'Upoopia!')

#-------------------------------------------------------------------------------
@link('!stop')
@modal.when_mode('upoopia')
def h_stop(bot, id, target, args, full_msg):
    modal.clear_mode(target)
    chans.remove(target.lower())
    reply(bot, id, target, 'Upoopia stopped.')

#-------------------------------------------------------------------------------
@link('CONTEND_MODE')
@modal.when_mode('upoopia')
def h_contend_mode(bot, id, target):
    reply(bot, id, target,
        'A game of Upoopia is currently in progress. Use !stop to end it.')
