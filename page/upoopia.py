#===============================================================================
# upoopia.py - an IRC implementation of http://www.unicorn7.org/games/game/553

import re

from untwisted.magic import sign

from upoopia_lib import *
from message import reply
import util
import modal
import chan_link

link = util.LinkSet()

# chan.lower() in mode_chans if 'upoopia' mode is active in chan.
mode_chans = set()

# challenges[ch1.lower()] = (ch2, WHITE or BLACK or None)
challenges = dict()

# games[ch1.lower()] == games[ch2.lower()] == game
# where instanceof(UpoopiaText, game)
#   and game.players[BLACK].lower() == ch1.lower()
#   and game.players[WHITE].lower() == ch2.lower()
games = dict()

#-------------------------------------------------------------------------------
def install(bot):
    try:
        chan_link.install(bot)
    except util.AlreadyInstalled:
        pass
    link.install(bot)

def uninstall(bot):
    link.uninstall(bot)

def reload(prev):
    if hasattr(prev, 'mode_chans') and isinstance(prev.mode_chans, set):
        mode_chans.update(prev.mode_chans)
        for chan in mode_chans: modal.set_mode(chan, 'upoopia')
    if hasattr(prev, 'challenges') and isinstance(prev.challenges, dict):
        challenges.update(prev.challenges)
    if hasattr(prev, 'games') and isinstance(games, dict):
        new_games = dict()
        for chan, game in prev.games.iteritems():
            if game not in new_games:
                new_games[game] = UpoopiaText(prev=game)
            games[chan] = new_games[game]

#-------------------------------------------------------------------------------
def send_msgs(bot, targets, *msgs):
    for msg in msgs:
        for target in targets:
            bot.send_msg(target, msg)

#-------------------------------------------------------------------------------
@link('HELP')
def h_help(bot, reply, *args):
    reply('upoopia #CHANNEL [black|white]',
    'Challenge #CHANNEL to a game of Upoopia.')

@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('upoopia #CHANNEL [b[lack]|w[hite]]',
    '    Challenge #CHANNEL to a game of Upoopia:'
    ' <http://www.unicorn7.org/games/game/553/>. To play on IRC, each player'
    ' must be in a separate channel with operator status, then each player'
    ' must send a challenge to the other channel, optionally indicating their'
    ' preferred colour, where, by convention, Black moves first.')

@link('!upoopia')
def h_upoopia(bot, id, target, args, full_msg):
    if not target: return

    # Parse arguments.
    args = args.split()
    if len(args) >= 2:
        opp_chan, colour = args[:2]
        if 'black'.startswith(colour.lower()):
            colour = BLACK
        elif 'white'.startswith(colour.lower()):
            colour = WHITE
        else:
            reply(bot, id, target,
                'Error: "%s" is not recognised as "black" or "white".' % colour)
            return
    elif len(args) >= 1:
        opp_chan, colour = args[0], None
    else:
        if target.lower() in challenges:
            opp_chan, colour = challenges[target.lower()]
            bot.send_msg(target,
                'A challenge issued to %s is currently pending.' % opp_chan)
        elif target.lower() in games:
            game = games[target.lower()]
            [opp] = [chan for chan in game.names.values()
                     if chan.lower() != target.lower()]
            bot.send_msg(target,
                'A game of Upoopia against %s is currently in session.' % opp)
        else:
            bot.send_msg(target,
                'No game of Upoopia is active. See "help upoopia" to start one.')

    if not opp_chan.startswith('#'):
        reply(bot, id, target,  
            'Error: "%s" is not a valid channel name.' % opp_chan)
        return

    # Enter 'upoopia' mode in this channel.
    if modal.get_mode(target):
        yield sign('CONTEND_MODE', bot, id, target)
        return
    modal.set_mode(target, 'upoopia')
    mode_chans.add(target.lower())

    # Initiate the game, if a reciprocating challenge exists.
    if opp_chan.lower() in challenges:
        opp_opp_chan, opp_colour = challenges[opp_chan.lower()]
        if opp_opp_chan.lower() == target.lower():
            del challenges[opp_chan.lower()]
            yield util.sub(start_game(bot, target, opp_chan, colour, opp_colour))
            return

    # Record the challenge.
    challenges[target.lower()] = (opp_chan, colour)
    bot.send_msg(target,
        'Challenge issued: waiting for %s to reciprocate.' % opp_chan)

def start_game(bot, chan1, chan2, colour1, colour2):
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
    yield util.sub(show_board(bot, game))

#-------------------------------------------------------------------------------
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('[move] b[lack]|w[hite] l[eft]|r[ight]|u[p]|d[own] 1|2|3|4|5|6',
    '    Move the given worm in the given direction by the given number of steps.')

@link('!move', '!')
@modal.when_mode('upoopia')
def h_move(bot, id, target, args, full_msg):
    raise NotImplemented

#-------------------------------------------------------------------------------
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('xray [1|2|3|4|5|6]',
    '    Sacrifice one of your dice of the opponent\'s colour in exchange for the'
    ' ability to see their dice for the remainder of this round.')

@link('!xray')
@modal.when_mode('upoopia')
def h_xray(bot, id, target, args, full_msg):
    raise NotImplemented

#-------------------------------------------------------------------------------
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('resign',
    '    Surrender the game to your opponent.')

@link('!resign')
@modal.when_mode('upoopia')
def h_resign(bot, id, target, args, full_msg):
    raise NotImplemented

#-------------------------------------------------------------------------------
@link(('HELP', 'upoopia'))
def h_help_upoopia(bot, reply, *args):
    reply('board',
    '    Show the state of the current board.')

@link('!board')
@modal.when_mode('upoopia')
def h_board(bot, id, chan, args, full_msg):
    if chan.lower() not in games: return
    game = games[chan.lower()]
    yield util.sub(show_board(bot, game))

def show_board(bot, game):
    for colour in game.player, other_colour(game.player):
        chan = game.names[colour]
        for line in game.game_lines(viewer=colour):
            bot.send_msg(chan, line)
        if colour == game.player:
            bot.send_msg(chan,
                '\2%s, it is your move. You are playing as %s.\2'
                    % (chan, colour))
        else:
            bot.send_msg(chan,
                'Waiting for %s to move.' % game.names[game.player])

#-------------------------------------------------------------------------------
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
    # Cancel any existing game.
    if chan.lower() in games:
        game = games[chan.lower()]
        for game_chan in game.names.itervalues():
            del games[game_chan.lower()]
            bot.send_msg(game_chan, 'The game of Upoopia has been cancelled.')
    # Release the channel mode.
    modal.clear_mode(chan)
    mode_chans.remove(chan.lower())

#-------------------------------------------------------------------------------
@link('CONTEND_MODE')
@modal.when_mode('upoopia')
def h_contend_mode(bot, id, target):
    reply(bot, id, target,
        'A game of Upoopia is currently in progress. Use !cancel to end it.')
