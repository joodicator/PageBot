#===============================================================================
# upoopia.py - an IRC implementation of http://www.unicorn7.org/games/game/553

import re

from untwisted.magic import sign

from upoopia_lib import *
from message import reply
import util
import modal
import channel
import chan_link
import runtime

link, install, uninstall = util.LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'chan_link')

# challenges[ch1.lower()] = (ch2, WHITE or BLACK or None)
challenges = dict()

# games[ch1.lower()] == games[ch2.lower()] == game
# where isinstance(game, UpoopiaText)
#   and game.players[BLACK].lower() == ch1.lower()
#   and game.players[WHITE].lower() == ch2.lower()
games = dict()

#-------------------------------------------------------------------------------
def reload(prev):
    if hasattr(prev, 'challenges') and isinstance(prev.challenges, dict):
        for chan, challenge in prev.challenges.iteritems():
            challenges[chan] = challenge
            modal.set_mode(chan, 'upoopia')
    if hasattr(prev, 'games') and isinstance(games, dict):
        new_games = dict()
        for chan, game in prev.games.iteritems():
            if game not in new_games:
                new_games[game] = UpoopiaText(prev=game)
            games[chan] = new_games[game]
            modal.set_mode(chan, 'upoopia')

#-------------------------------------------------------------------------------
# !upoopia
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('upoopia #CHANNEL [b[lue]|r[ed]]',
    '    Challenge #CHANNEL to a game of Upoopia:'
    ' <http://www.unicorn7.org/games/game/553/>. To play on IRC, each player'
    ' must be in a separate channel with operator status, then each player'
    ' must send a challenge to the other channel, optionally indicating their'
    ' preferred colour, where, by convention, Blue moves first.')
    reply('upoopia',
    '    With no arguments, start a new game with the last channel played.')

@link('!upoopia')
def h_upoopia(bot, id, chan, args, full_msg):
    if not chan: return

    # Parse arguments.
    args = args.split()
    if len(args) >= 2:
        opp_chan, colour = args[:2]
        if 'blue'.startswith(colour.lower()):
            colour = BLACK
        elif 'red'.startswith(colour.lower()):
            colour = WHITE
        else:
            reply(bot, id, chan,
                'Error: "%s" is not a valid colour.' % colour)
            return
    elif len(args) >= 1:
        opp_chan, colour = args[0], None
    elif len(chan_link.links.get(chan.lower(), set())) == 1:
        # Implicitly select the single channel to which we are linked.
        [opp_chan], colour = chan_link.links[chan.lower()], None
    else:
        if chan.lower() in challenges:
            opp_chan, colour = challenges[chan.lower()]
            bot.send_msg(chan,
                'A challenge issued to %s is currently pending.' % opp_chan)
        elif chan.lower() in games:
            game = games[chan.lower()]
            [opp] = [chan for chan in game.names.values()
                     if chan.lower() != chan.lower()]
            bot.send_msg(chan,
                'A game of Upoopia against %s is currently in session.' % opp)
        else:
            bot.send_msg(chan,
                'No game of Upoopia is active.'
                ' See \2!help upoopia\2 for starting a game.')
        return

    if not opp_chan.startswith('#'):
        reply(bot, id, chan,  
            'Error: "%s" is not a valid channel name.' % opp_chan)
        return
    elif opp_chan.lower() == chan.lower():
        reply(bot, id, chan,
            'Error: your opponent must be in a different channel!')
        return

    # If not already linked, require operator status.
    if not chan_link.is_linked(chan, opp_chan):
        pre_ms, pre_cs = bot.isupport['PREFIX']
        umodes = channel.umode_channels[chan.lower()]
        umodes = umodes.get(id.nick.lower(), '')
        if not any(m in umodes for m in pre_ms[:pre_ms.find('o')+1]):
            reply(bot, id, chan,
                'Error: only channel operators may initiate a channel link.')
            return

    # Acquire the 'upoopia' mode in this channel.
    if modal.get_mode(chan) == 'upoopia' and chan.lower() in challenges:
        # If another challenge exists, cancel it.
        old_opp_chan, colour = challenges.pop(chan.lower())
        bot.send_msg(chan, 'Challenge to %s cancelled.' % old_opp_chan)
    elif modal.get_mode(chan):
        yield sign('CONTEND_MODE', bot, id, chan)
        return
    else:
        modal.set_mode(chan, 'upoopia')

    if opp_chan.lower() in challenges:
        # If a reciprocating challenge exists, immediately start the game.
        opp_opp_chan, opp_colour = challenges[opp_chan.lower()]
        if opp_opp_chan.lower() == chan.lower():
            del challenges[opp_chan.lower()]
            yield util.sub(start_game(bot, chan, opp_chan, colour, opp_colour))
            return
    elif chan_link.is_linked(chan, opp_chan) \
    and modal.get_mode(opp_chan) in (None, 'upoopia'):
        # Otherwise, if the opponent channel is still linked and does not
        # have any pending challenges, also immediately start the game.
        modal.set_mode(opp_chan, 'upoopia')
        yield util.sub(start_game(bot, chan, opp_chan, colour, None))
        return

    # Otherwise, just record the challenge.
    challenges[chan.lower()] = (opp_chan, colour)
    bot.send_msg(chan,
        'Challenge issued: waiting for %s to reciprocate.' % opp_chan)

def start_game(bot, chan1, chan2, colour1, colour2):
    # Establish an exclusive channel link.
    for lchan in list(chan_link.links.get(chan1.lower(), set())):
        if lchan == chan2.lower(): continue
        yield chan_link.del_link(bot, chan1, lchan)
    for lchan in list(chan_link.links.get(chan2.lower(), set())):
        if lchan == chan1.lower(): continue
        yield chan_link.del_link(bot, chan2, lchan)
    yield chan_link.add_link(bot, chan1, chan2)

    # Decide colours.
    if colour1 == colour2:
        colour1 = random.choice((BLACK, WHITE))
        colour2 = other_colour(colour1)
    elif colour1 is None:
        colour1 = other_colour(colour2)
    elif colour2 is None:
        colour2 = other_colour(colour1)

    # Start game.
    game = UpoopiaText(
        black_name = chan1 if colour1 == BLACK else chan2,
        white_name = chan1 if colour1 == WHITE else chan2)
    games[chan1] = games[chan2] = game
    yield show_board(bot, game, priority=BLACK)

#-------------------------------------------------------------------------------
# !move
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('[move] b[lue]|r[ed] l[eft]|r[ight]|u[p]|d[own] 1|2|3|4|5|6',
    '    Use a die of the given colour and value to move the worm of the same'
    ' colour over the same distance, in the given direction.')

@link('!b', '!blue', a=lambda args: 'b ' + args)
@link('!r', '!red',  a=lambda args: 'r ' + args)
@link('!', '!move',  a=lambda args: args)
@modal.when_mode('upoopia')
def h_move(bot, id, chan, args, full_msg, **kwds):
    if chan.lower() not in games: return
    game = games[chan.lower()]
    if chan.lower() != game.names[game.player].lower(): reply(bot, id, chan,
        'Error: it is not your turn.'); return

    args = kwds['a'](args).split()
    if len(args) < 3: reply(bot, id, chan,
        'Error: 3 parameters expected. See "help upoopia".'); return

    colour, direction, value = args[:3]
    if direction in '123456': value, direction = direction, value

    if 'blue'.startswith(colour.lower()): colour = BLACK
    elif 'red'.startswith(colour.lower()): colour = WHITE
    else: reply(bot, id, chan,
        'Error: "%s" is not a valid colour.' % colour); return

    if value in '123456': value = int(value)
    else: reply(bot, id, chan,
        'Error: "%s" is not a valid distance.' % value); return

    if    'left'.startswith(direction.lower()): direction = LEFT
    elif 'right'.startswith(direction.lower()): direction = RIGHT
    elif    'up'.startswith(direction.lower()): direction = UP
    elif  'down'.startswith(direction.lower()): direction = DOWN
    else: reply(bot, id, chan,
        'Error: "%s" is not a valid direction.' % direction); return

    try:
        game.move(colour, value, direction)
    except IllegalMove as e:
        reply(bot, id, chan, 'Error: %s' % e)
        return

    yield util.sub(end_move(bot, game))

def end_move(bot, game):
    yield show_board(bot, game, priority=game.winner or game.player)
    if game.winner:
        chan1, chan2 = game.names.values()
        del games[chan1]
        del games[chan2]
        yield util.sub(end_session(bot, chan1, chan2))

#-------------------------------------------------------------------------------
# !xray
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('xray [1|2|3]',
    '    Sacrifice one of your dice of the opponent\'s colour in exchange'
    ' for the ability to see their dice for the remainder of this round.')

@link('!xray')
@modal.when_mode('upoopia')
def h_xray(bot, id, chan, args, full_msg):
    if chan.lower() not in games: return
    game = games[chan.lower()]
    if chan.lower() != game.names[game.player].lower(): reply(bot, id, chan,
        'Error: it is not your turn.'); return

    args = args.split()
    if args:
        value = args[0]
        if value in '123': value = int(value)
        else: reply(bot, id, chan,
            'Error: "%s" is not a valid 3-sided die value.' % value); return
    else:
        player, opponent = game.player, other_colour(game.player)
        values = [dv for (dc,dv) in game.dice[player] if dc == opponent]
        if not values: reply(bot, id, chan,
            'Error: %s does not possess any %s dice.'
            % (player, opponent.lower())); return
        if not all(v == values[0] for v in values[1:]): reply(bot, id, chan,
            'Error: %s has %s dice with different values; you must specify'
            ' the value to sacrifice.' % (player, opponent.lower())); return
        value = values[0]

    try:
        game.xray(value)
    except IllegalMove as exc:
        reply(bot, id, chan, 'Error: %s' % exc)
        return
    yield util.sub(end_move(bot, game))

#-------------------------------------------------------------------------------
# !resign
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('resign',
    '    Surrender the game to your opponent.')

@link('!resign')
@modal.when_mode('upoopia')
def h_resign(bot, id, chan, args, full_msg):
    if chan.lower() not in games: return
    game = games[chan.lower()]
    if chan.lower() != game.names[game.player].lower(): reply(bot, id, chan,
        'Error: it is not your turn.'); return
    try:
        game.resign()
    except IllegalMove as exc:
        reply(bot, id, chan, 'Error: %s' % exc)
        return
    yield util.sub(end_move(bot, game))

#-------------------------------------------------------------------------------
# !board
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('board',
    '    Show the state of the current board.')

@link('!board')
@modal.when_mode('upoopia')
def h_board(bot, id, chan, args, full_msg):
    if chan.lower() not in games: return
    game = games[chan.lower()]
    colour = WHITE if game.names[WHITE].lower() == chan.lower() else BLACK
    yield show_board(bot, game, priority=colour)

@util.msub(link, 'upoopia.show_board')
def show_board(bot, game, priority=None):
    yield runtime.sleep(0)
    lines = { BLACK:[], WHITE:[] }
    for colour in BLACK, WHITE:
        chan = game.names[colour]
        lines[colour].extend(game.game_lines(viewer=colour, irc=True))
    if priority:
        for colour in priority, other_colour(priority):
            for line in lines[colour]:
                bot.send_msg(game.names[colour], line, no_link=True)
    else:
        for b_line, w_line in izip_longest(lines[BLACK], lines[WHITE]):
            if b_line: bot.send_msg(game.names[BLACK], b_line, no_link=True)
            if w_line: bot.send_msg(game.names[WHITE], w_line, no_link=True)

#-------------------------------------------------------------------------------
# !cancel
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('cancel',
    '    Retract a challenge, or end the game without declaring a winner.')

@link('!cancel')
@modal.when_mode('upoopia')
def h_cancel(bot, id, chan, args, full_msg):
    # Cancel any existing challenge.
    if chan.lower() in challenges:
        opp_chan, colour = challenges.pop(chan.lower())
        reply(bot, id, chan,
            'Challenge to %s cancelled.' % opp_chan, prefix=False)
        yield util.sub(end_session(bot, chan))
    # Cancel any existing game.
    if chan.lower() in games:
        game = games[chan.lower()]
        [opp_chan] = [c for c in game.names.values() if c.lower()!=chan.lower()]
        for game_chan in game.names.itervalues():
            del games[game_chan.lower()]
            bot.send_msg(game_chan,
                'The game of Upoopia has been cancelled.', no_link=True)
        yield util.sub(end_session(bot, chan, opp_chan))

def end_session(bot, chan, opp_chan=None):
    if opp_chan:
        chan_link.decay_link(bot, chan, opp_chan)
        modal.clear_mode(opp_chan)
    modal.clear_mode(chan)

#-------------------------------------------------------------------------------
@link('CONTEND_MODE')
@modal.when_mode('upoopia')
def h_contend_mode(bot, id, target):
    reply(bot, id, target,
        'A game of Upoopia is currently in progress.'
        ' Use \2!cancel\2 to end it.')

@link('SELF_PART', 'SELF_KICKED')
def h_self_exit(bot, chan, *args):
    if chan.lower() in challenges:
        del challenges[chan.lower()]
        yield util.sub(end_session(bot, chan))
