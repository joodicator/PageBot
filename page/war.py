import util
import message
from auth import admin

import pickle
import os.path
from collections import defaultdict
from war_state import *

link, install, uninstall = util.LinkSet().triple()

STATE = 'state/war.pickle'
state = None

def init_state():
    return defaultdict(State)

def load_state():
    global state
    if state: return state
    try:
        with open(STATE, 'r') as file: state = pickle.load(file)
    except (EOFError, IOError, pickle.UnpicklingError):
        state = init_state()
    return state

def save_state(state):
    with open(STATE, 'w') as file:
        pickle.dump(state, file)

def get_state(key):
    return load_state()[key]

def put_state(key, val):
    state = load_state()
    state[key] = val
    save_state(state)


@link('HELP')
def h_help(bot, reply, args):
    reply('war [WIDTH [HEIGHT]]',   'Starts a new game of WAR OF LIFE.')
    reply('move [FROM TO]',         'Issues a move in WAR OF LIFE.')


@link('!war_reset')
@admin
def h_war_reset(bot, id, target, args, full_msg):
    save_state(init_state())
    message.reply(bot, id, target, 'Done.')


@link('!war_print')
def h_war(bot, id, target, args, full_msg):
    try:
        game = get_state(target or id)
        if not game.active: return
        reply = lambda msg: message.reply(bot, id, target, msg, prefix=False)
        game.show_update(reply)
    except Exception as e:
        reply(str(e) or repr(e))
        raise


@link(('HELP', 'war'))
def h_help_war(bot, reply, args):
    reply('war [WIDTH [HEIGHT]]',
    'Starts a new game of WAR OF LIFE on a board with the given dimensions,'
    ' or a square board if only WIDTH is given, or otherwise an 8*8 board.')

@link('!war')
def h_war(bot, id, target, args, full_msg):
    try:
        game = get_state(target or id)
        reply = lambda msg: message.reply(bot, id, target, msg, prefix=False)
        game.begin(*re.split(r'\s+', args))
        game.show_intro(reply)
        game.show_update(reply)
        put_state(target or id, game)
    except Exception as e:
        reply(str(e) or repr(e))
        raise


@link(('HELP', 'move'))
def h_help_move(bot, reply, args):
    reply('move [FROM TO]',
    'If WAR OF LIFE is active, issues a move from the given board coordinate'
    ' to the given destination, or if used without parameters, passes.')
    reply('',
    'Example: !move a1 h8')

@link('!move')
def h_move(bot, id, target, args, full_msg):
    try:
        game = get_state(target or id)
        if not game.active: return
        reply = lambda msg: message.reply(bot, id, target, msg, prefix=False)
        if args:
            game.move(*re.split(r'\s+', args))
        else:
            game.pass_move()
        game.show_update(reply)    
        put_state(target or id, game)
    except Exception as e:
        reply(str(e))
        raise
