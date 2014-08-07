#===============================================================================
# uppoopa_lib.py - reusable components of upoopia.py.

from itertools import *
import random

import util

#---------------------------------------------------------------------------
# Constants representing aspects of the state of a Upoopia game, whose string
# values also give a human-readable text representation.
BLACK, WHITE = 'Black', 'White'
LEFT, RIGHT, UP, DOWN = (-1,0), (1,0), (0,-1), (0,1)

WIDTH, HEIGHT = 19, 10
WORM = { BLACK:'X', WHITE:'O' }
POOP = { BLACK:'x', WHITE:'o' }
GLXY = { BLACK:'+', WHITE:'=' }
DIE  = { BLACK:'B', WHITE:'W' }
BHOLE, EMPTY = '@', '.'

#-------------------------------------------------------------------------------
# Utility functions.
def other_colour(colour):
    return WHITE if colour == BLACK else BLACK

def roll_die(die_colour, owner_colour):
    sides = 6 if die_colour == owner_colour else 3
    return (die_colour, random.randint(1, sides))

#-------------------------------------------------------------------------------
# Hierarcy of exceptions related to Upoopia.
class UpoopiaError(Exception): pass
class IllegalMove(UpoopiaError): pass


#===============================================================================
# The essential state of an ongoing game of Upoopia.
class Upoopia(object):
    __slots__ = (
        'round_beginner', # round_beginner in {BLACK,WHITE}
        'round_number',   # round_number >= 1, or 0 if not started.
        'names',          # names[c] in {string,None}, c in {BLACK,WHITE}
        'player',         # player in {BLACK, WHITE}
        'winner',         # winner in {BLACK, WHITE, NONE}
        'resigned',       # resigned in {True, False}
        'worm',           # worm[colour] == x,y --> board[x,y] == WORM[colour]
        'direction',      # direction[colour] in {LEFT, RIGHT, UP, DOWN}
        'dice',           # dice[colour] == [(die_colour,value), ...]
        'galaxies',       # galaxies[colour] == [GLXY[galaxy_colour], ...]
        'has_xray',       # xray[colour] in {True,False}
        'board' )         # board.get((x,y), EMPTY)
                          #   in {WORM[c], POOP[c], GLXY[c], BHOLE, EMPTY}
                          #   for 1<=x<=WIDTH, 1<=y<=HEIGHT, c in {BLACK,WHITE}

    def __init__(self, *args, **kwds):
        if 'prev' in kwds:
            self.init_reload(*args, **kwds)
        else:
            self.init_normal(*args, **kwds)

    def init_reload(self, prev):
        self.init_normal()
        for attr in Upoopia.__slots__:
            if hasattr(prev, attr):
                setattr(self, attr, getattr(prev, attr))

    def init_normal(self, black_name=None, white_name=None, first_player=BLACK ):
        self.round_beginner = first_player
        self.round_number = 1
        self.names = { BLACK:black_name, WHITE:white_name }
        self.player = first_player
        self.winner = None
        self.resigned = False
        self.worm = { WHITE:(17,8), BLACK:(03,8) }
        self.direction = { BLACK:RIGHT, WHITE:LEFT }
        self.dice = { BLACK:[], WHITE:[] }
        self.galaxies = { BLACK:[], WHITE:[] }
        self.has_xray = { BLACK:False, WHITE:False }
        self.board = {
            self.worm[BLACK]:WORM[BLACK],
            self.worm[WHITE]:WORM[WHITE],
            (01,8):POOP[BLACK], (02,8):POOP[BLACK],
            (19,8):POOP[WHITE], (18,8):POOP[WHITE],
            (04,4):GLXY[BLACK], (16,4):GLXY[WHITE],
            (10,4):BHOLE, (10,8):BHOLE }
        self._start_round()

    #---------------------------------------------------------------------------
    # If this constitutes a legal move, and the player possesses a corresponding
    # die, move the "colour" worm "length" units (or half, as appropriate) in
    # "direction", remove the die, and end the current player's turn.
    def move(self, colour, value, direction):
        if self.winner:
            raise IllegalMove('the game is over.')
        if (colour,value) not in self.dice[self.player]:
            raise IllegalMove('%s does not possess a %s die of value %s.'
                % (self.player, colour.lower(), value))
        self._just_move(colour, value, direction)
        self.dice[self.player].remove((colour,value))
        self._end_turn()

    #---------------------------------------------------------------------------
    # If this constitutes a legal move, sacrifice a die possessed by the current
    # player, of the opposite colour to them, and with the given value,
    # in exchange for allowing them to see their opponents' dice.
    def xray(self, die_value):
        die = (other_colour(self.player), die_value)
        if die not in self.dice[self.player]:
            raise IllegalMove('%s does not possess a %s die of value %s.'
                % (self.player, other_colour(self.player).lower(), die_value))
        self.dice[self.player].remove(die)
        self.has_xray[self.player] = True
        self._end_turn()

    #---------------------------------------------------------------------------
    # Cause the current player to lose the game by resignation.
    def resign(self):
        self._loss(self.player, resign=True)

    #---------------------------------------------------------------------------
    # If this constitutes a legal move (ignoring the current player and their
    # dice), move "colour" worm "length" units in direction "dx,dy", possibly
    # resulting in the player "colour" losing the game; else, raise IllegalMove.
    def _just_move(self, colour, length, (dx,dy)):
        prev_dx, prev_dy = self.direction[colour]
        if (-prev_dx, -prev_dy) == (dx, dy):
            raise IllegalMove('worms may not move backwards.')

        x, y = self.worm[colour]
        for i in range(length):
            self.board[x, y] = POOP[colour]
            x, y = (x+dx-1)%WIDTH+1, (y+dy-1)%HEIGHT+1
            target = self.board.get((x,y), EMPTY)
            if target in GLXY.itervalues():
                # Pick up a galaxy.
                self.galaxies[colour].append(target)
            elif target != EMPTY:
                # Run into an obstacle.
                x, y = (x-dx-1)%WIDTH+1, (y-dy-1)%HEIGHT+1
                self._loss(colour)
                break

        self.board[x, y] = WORM[colour]
        self.worm[colour] = x, y
        self.direction[colour] = dx, dy

    #---------------------------------------------------------------------------
    # Start a new round of gameplay, without adjusting the current player,
    # round beginner or round number, or x-ray status.
    def _start_round(self):
        for colour in BLACK, WHITE:
            # Roll standard dice.
            self.dice[colour][:] = [
                roll_die(colour, colour),
                roll_die(colour, colour),
                roll_die(other_colour(colour), colour) ]

            # Roll dice for any galaxies held.
            for galaxy in self.galaxies[colour]:
                for galaxy_colour in BLACK, WHITE:
                    if galaxy != GLXY[galaxy_colour]: continue
                    self.dice[colour].append(roll_die(galaxy_colour, colour))
                    break
                else: raise Exception('invalid galaxy: %s' % galaxy)
            self.galaxies[colour] = []

    #---------------------------------------------------------------------------
    # End the current round of gameplay and start a new round.    
    def _end_round(self):
        self.round_beginner = other_colour(self.round_beginner)
        self.player = self.round_beginner
        self.round_number += 1
        self.has_xray[BLACK] = False
        self.has_xray[WHITE] = False
        self._start_round()

    #---------------------------------------------------------------------------
    # End the current player's turn.
    def _end_turn(self):
        other_player = other_colour(self.player)
        if self.dice[other_player]:
            # Other player has some dice.
            self.player = other_player
        elif not self.dice[self.player]:
            # Neither player has any dice.
            self._end_round()
    
    #---------------------------------------------------------------------------
    # Cause the given player to lose the game, possibly by resignation.
    def _loss(self, colour, resign=False):
        self.resigned = resign
        self.winner = other_colour(colour)


#===============================================================================
# A game of Upoopia, equipped to produce text representations of its state.
class UpoopiaText(Upoopia):
    def __init__(self, *args, **kwds):
        Upoopia.__init__(self, *args, **kwds)
    
    # Return a list of strings giving rows in a (monospaced) text representation
    # of the current game state. If "viewer" is given as BLACK or WHITE, only
    # the information visible to that player is shown in the output.
    def game_lines(self, viewer=None, **kwds):
        return util.join_cols(
            self.board_lines(viewer, **kwds),
            self.status_lines(viewer, **kwds)
            + self.legend_lines(viewer, **kwds))

    def board_lines(self, viewer=None, **kwds):
        lines = []
        for y in xrange(1,HEIGHT+1):
            chs, bold, red = [], False, False
            for x in xrange(1,WIDTH+1):
                symbol = self.board.get((x, y), EMPTY)
                if symbol in 
            lines.append(' '.join(chs)) 
        return lines

    def status_lines(self, viewer=None, **kwds):
        if self.winner: return [
            '',
            '%(bo)sGame over!%(bo)s' % {
                'bo': '\2' if kwds.get('irc') else ''},
            '',
            '%(bo)%(pl)s%(pn)s wins%(re)s.%(bo)s' % {
                'bo': '\2' if kwds.get('irc') else '',
                'pl': self.winner,
                'pn': ' (%s)' % self.names[self.winner]
                      if self.names[self.winner] else '',
                're': ' by resignation' if self.resigned else ''},
            '']
        else: return [
            '%(pl)s to play (round %(rn)s, started by %(rb)s)' % {
                'pl': self.player,
                'rn': self.round_number,
                'rb': self.round_beginner },
            '',
            '%(bo)s%(pl)s%(pn)s: %(is)s%(bo)s' % {
                'bo': '\2' if viewer == self.player == BLACK
                           and kwds.get('irc') else '',
                'pl': BLACK,
                'pn': ' (%s)' % self.names[BLACK] if self.names[BLACK] else '',
                'is': ', '.join(self.item_names(BLACK, viewer, **kwds)) },
            '%(bo)s%(pl)s%(pn)s: %(is)s%(bo)s' % {
                'bo': '\2' if viewer == self.player == WHITE
                           and kwds.get('irc') else '',
                'pl': WHITE,
                'pn': ' (%s)' % self.names[WHITE] if self.names[WHITE] else '',
                'is': ', '.join(self.item_names(WHITE, viewer, **kwds)) },
            '']

    def legend_lines(self, viewer=None, **kwds):
        return util.join_rows(
            ['%s black die'    % DIE[BLACK],  '%s white die'    % DIE[WHITE]],
            ['%s black worm'   % WORM[BLACK], '%s white worm'   % WORM[WHITE]],
            ['%s black poop'   % POOP[BLACK], '%s white poop'   % POOP[WHITE]],
            ['%s black galaxy' % GLXY[BLACK], '%s white galaxy' % GLXY[WHITE]],
            ['%s black hole'   % BHOLE,       '%s empty'        % EMPTY] )

    def item_names(self, player, viewer=None, **kwds):
        sorted_dice = sorted(self.dice[player],
            key=lambda (dc,dv): (0 if dc == player else 1, dv))
        for (die_colour, value) in sorted_dice:
            if viewer is None or viewer == player or self.has_xray[viewer]:
                yield '%s(%s)' % (DIE[die_colour], value)
            else:
                yield '%s(?)' % DIE[die_colour]
        for galaxy in self.galaxies[player]:
            yield galaxy
        if self.has_xray[player]:
            yield 'x-ray vision'
