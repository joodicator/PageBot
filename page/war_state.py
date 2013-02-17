import re
import random
import util
from itertools import *

class State(object):
    def __init__(self):
        self.active = False

    def init_board(self):
        return [[0 for y in xrange(self.height)] for x in xrange(self.width)]

    def copy_board(self, board):
        return [[board[x][y] for y in xrange(self.height)]
                for x in xrange(self.width)]

    def init_pieces(self, board, pieces):
        places = list(product(xrange(self.width), xrange(self.height)))
        places = random.sample(places, 2*pieces)
        for x, y in places[:pieces]:
            board[x][y] = 1
        for x, y in places[pieces:]:
            board[x][y] = 2

    def begin(self, width=None, height=None, pieces=None):
        self.width = int(width) if width else 8
        self.height = int(height) if height else self.width
        pieces = int(pieces) if pieces else 12        

        self.board = self.init_board()
        self.init_pieces(self.board, pieces)
        self.prev_board = self.copy_board(self.board)

        self.turn = 1
        self.active = True

    def move(self, p1, p2):
        [(x1, y1), (x2, y2)] = map(self.read_posn, [p1, p2])
        if max(abs(x1 - x2), abs(y1 - y2)) != 1: raise Exception(
            'Error: %s and %s are not neighbouring cells.' % (p1, p2))
        if self.board[x1][y1] != self.turn: raise Exception(
            'Error: %s is not a PLAYER %s piece.' % (p1, self.turn))
        if self.board[x2][y2] != 0: raise Exception(
            'Error: %s is not an empty cell.' % p2)
        self.prev_board = self.copy_board(self.board)
        self.board[x1][y1], self.board[x2][y2] = 0, self.turn
        self.crank_board()
        self.end_turn()

    def pass_move(self):
        self.prev_board = self.copy_board(self.board)
        self.crank_board()
        self.end_turn()

    def end_turn(self):
        self.turn = 1 if self.turn == 2 else 2

    def crank_board(self):
        def safe_board(x, y):
            return 0 if not (0 <= x < self.width and 0 <= y < self.height) \
                   else self.board[x][y]
        def new_cell(x, y):
            cur = self.board[x][y]
            nei = [0, 0, 0]
            for i, j in product((x-1, x, x+1), (y-1, y, y+1)):
                nei[safe_board(i, j)] += 1
            nei[cur] -= 1
            assert sum(nei) == 8
            if cur == 0 and 8 - nei[0] == 3:
                return 1 if nei[1] > nei[2] else 2
            elif not 2 <= 8 - nei[0] <= 3:
                return 0
            else:
                return cur                 
        board = [[new_cell(x, y) for y in xrange(self.width)]
                 for x in xrange(self.height)]
        self.board = board

    def read_posn(self, input):
        def fail():
            raise Exception('Error: "%s" is not a valid position.' % input)
        posn = input.lower()
        match = re.match(r'([a-z])(\d+)|(\d+)([a-z])', posn)
        if not match: fail()
        x, y = sorted(filter(lambda x: x, match.groups()), reverse=True)
        x, y = ord(x) - ord('a'), int(y) - 1
        if x >= self.width or y >= self.height: fail()
        return (x, y)

    def show_intro(self, reply):
        reply('Key:'
              ' x - PLAYER 1 piece;'
              ' X - new PLAYER 1 piece;'
              ' o - PLAYER 2 piece;'
              ' O - new PLAYER 2 piece;'
              ' . - empty cell;'
              ' _ - newly empty cell.')
    
    def show_update(self, reply):
        def showc(x, y):
            outx, outy = not 0 <= x < self.width, not 0 <= y < self.height
            if outx and outy: return ''
            if outx: return str(y + 1)
            if outy: return chr(ord('a') + x)
            return [
                ['.', 'X', 'O'],
                ['_', 'x', 'O'],
                ['_', 'X', 'o']
            ][self.prev_board[x][y]][self.board[x][y]]
        lines = [[showc(x, y) for x in xrange(-1, self.width + 1)]
                 for y in xrange(-1, self.height + 1)]
        for line in util.align_table(lines, sep=' ', align='r'):
            reply(line)
        reply('It is PLAYER %s\'s turn.' % self.turn)

