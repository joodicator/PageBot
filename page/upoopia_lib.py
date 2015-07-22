#===============================================================================
# uppoopa_lib.py - reusable components of upoopia.py.

from itertools import *
import random
import re

import util

#---------------------------------------------------------------------------
# Constants representing aspects of the state of a Upoopia game.
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

def strip_irc_len(text):
    codes = re.finditer(r'[\x02\x1f\x16\x0f]|\x03(\d\d?(,\d\d?)?)?', text)
    return len(text) - sum(len(m.group()) for m in codes)

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
            + self.legend_lines(viewer, **kwds),
            lenf=strip_irc_len) + ['---']

    def symbol_text(self, s, **kwds):
        return 'Blue' if s == BLACK else \
               'Red' if s == WHITE else \
               'B' if s == DIE[BLACK] else \
               'R' if s == DIE[WHITE] else \
               '#' if s == WORM[BLACK] else \
               '8' if s == WORM[WHITE] else \
               'x' if s == POOP[BLACK] else \
               'o' if s == POOP[WHITE] else \
               '$' if s == GLXY[BLACK] else \
               '%' if s == GLXY[WHITE] else \
               '@' if s == BHOLE else \
               '.' if s == EMPTY else None

    def symbol_colour(self, s, **kwds):
        return '12' if s in (WORM[BLACK],POOP[BLACK],DIE[BLACK],BLACK) \
          else '04' if s in (WORM[WHITE],POOP[WHITE],DIE[WHITE],WHITE) \
          else '10' if s == GLXY[BLACK] \
          else '06' if s == GLXY[WHITE] \
          else '14' if s == EMPTY else None

    def symbol_colour_text(self, s, **kwds):
        text = self.symbol_text(s)
        if kwds.get('irc'):
            colour = self.symbol_colour(s, **kwds)
            if colour: text = '\x03%s%s\x03' % (colour, text)
        return text

    def board_lines(self, viewer=None, **kwds):
        lines = []
        for y in xrange(1,HEIGHT+1):
            colour = None
            cells = []
            for x in xrange(1,WIDTH+1):
                symbol = self.board.get((x, y), EMPTY)
                new_colour = self.symbol_colour(symbol, **kwds)
                cell = self.symbol_text(symbol, **kwds)
                if colour != new_colour:
                    cell = '\x03' + (new_colour or '') + cell
                    colour = new_colour
                cells.append(cell)
            line = ' '.join(cells)
            if kwds.get('irc') and colour: line += '\x0f'
            lines.append(line)
        return lines

    def status_lines(self, viewer=None, **kwds):
        if self.winner:
            return [
                '',
                '%(bo)sGame over!%(bo)s' % {
                    'bo': '\x02' if kwds.get('irc') else ''},
                '',
                '%(bo)s%(pl)s%(pn)s wins%(re)s.%(bo)s' % {
                    'bo': '\x02' if kwds.get('irc') else '',
                    'pl': self.symbol_text(self.winner, **kwds),
                    'pn': ' (%s)' % self.names[self.winner]
                          if self.names[self.winner] else '',
                    're': ' by resignation' if self.resigned else ''},
                '']
        else:
            h_black = viewer == self.player == BLACK and kwds.get('irc')
            h_white = viewer == self.player == WHITE and kwds.get('irc')
            return [
                '%(pl)s to play (round %(rn)s, started by %(rb)s)' % {
                    'pl': self.symbol_text(self.player, **kwds),
                    'rn': self.round_number,
                    'rb': self.symbol_text(self.round_beginner, **kwds) },
                '',
                '%(cs)s%(pl)s%(pn)s: %(is)s%(ce)s' % {
                    'cs': '\x03'+self.symbol_colour(BLACK) if h_black else '',
                    'ce': '\x03' if h_black else '',
                    'pl': self.symbol_text(BLACK, **kwds),
                    'pn': ' (%s)' % self.names[BLACK] if self.names[BLACK] else '',
                    'is': ', '.join(self.item_names(BLACK, viewer, **kwds)) },
                '%(cs)s%(pl)s%(pn)s: %(is)s%(ce)s' % {
                    'cs': '\x03'+self.symbol_colour(WHITE) if h_white else '',
                    'ce': '\x03' if h_white else '',
                    'pl': self.symbol_text(WHITE, **kwds),
                    'pn': ' (%s)' % self.names[WHITE] if self.names[WHITE] else '',
                    'is': ', '.join(self.item_names(WHITE, viewer, **kwds)) },
                '']

    def legend_lines(self, viewer=None, **kwds):
        s = lambda s: self.symbol_text(s, **kwds)
        black, white = s(BLACK).lower(), s(WHITE).lower()
        return util.join_rows(
            ['%s %s die'     % (s(DIE[BLACK]), black),
             '%s %s die'     % (s(DIE[WHITE]), white)
            ],
            ['%s %s worm'    % (s(WORM[BLACK]), black),
             '%s %s worm'    % (s(WORM[WHITE]), white)
            ],
            ['%s %s poop'    % (s(POOP[BLACK]), black),
             '%s %s poop'    % (s(POOP[WHITE]), white)
            ],
            ['%s %s galaxy'  % (s(GLXY[BLACK]), black),
             '%s %s galaxy'  % (s(GLXY[WHITE]), white),
            ],
            ['%s black hole' % s(BHOLE),
             '%s empty'      % s(EMPTY)
            ],
            lenf=strip_irc_len)

    def item_names(self, player, viewer=None, **kwds):
        sorted_dice = sorted(self.dice[player],
            key=lambda (dc,dv): (0 if dc == player else 1, dv))
        for (die_colour, value) in sorted_dice:
            if viewer is None or viewer == player or self.has_xray[viewer]:
                text = '%s(%s)' % (
                    self.symbol_text(DIE[die_colour], **kwds),
                    value)
            else:
                text = '%s(%s)' % (
                    self.symbol_text(DIE[die_colour], **kwds),
                    '?')
#            colour = self.symbol_colour(DIE[die_colour], **kwds)
#            if colour and kwds.get('irc'):
#                text = '\x03%s%s\x03' % (colour, text)
            yield text
        for galaxy in self.galaxies[player]:
            yield self.symbol_text(galaxy, **kwds)
        if self.has_xray[player]:
            yield 'x-ray vision'
