from importlib import import_module
from util import LinkSet, deep_reload
from auth import admin
import sys
import re

link, install, uninstall = LinkSet().triple()

def echo(bot, id, target, args):
    if target is None: target = id.nick
    bot.send_msg(target, args)

@link('!echo')
@admin
def _echo(bot, id, target, args, full_msg):
    echo(bot, id, target, args)

@link('!raw')
@admin
def _raw(bot, id, target, args, full_msg):
    bot.send_cmd(args)

@link('!msg')
@admin
def _msg(bot, id, target, args, full_msg):
    match = re.match('(?P<whom>\S*)\s*(?P<msg>.*)$', args)
    bot.send_msg(*match.group('whom', 'msg'))

@link('!j')
@link('!join')
@admin
def _join(bot, id, target, args, full_msg):
    bot.send_cmd('JOIN :%s' % args)

@link('!part')
@admin
def _part(bot, id, target, args, full_msg):
    bot.send_cmd('PART :%s' % (args or target))

@link('!eval')
@admin
def _eval(bot, id, target, args, full_msg):
    try:
        result = eval(args)
    except Exception as e:
        result = e
    echo(bot, id, target, repr(result))

@link('!exec')
@admin
def _exec(bot, id, target, args, full_msg):
    try:
        exec args
    except Exception as e:
        echo(bot, id, target, repr(e))

@link('!load')
@admin
def _load(bot, id, target, args, full_msg):
    try:
        mod = import_module(args)
        if hasattr(mod, 'install'): mod.install(bot)
    except ImportError as e:
        echo(bot, id, target, repr(e))
    echo(bot, id, target, 'Done.')

@link('!unload')
@admin
def _unload(bot, id, target, args, full_msg):
    try:
        mod = sys.modules[args]
        if hasattr(mod, 'uninstall'): mod.uninstall(bot)
    except KeyError as e:
        echo(bot, id, target, repr(e))
    echo(bot, id, target, 'Done.')

@link('!reload')
@admin
def _reload(bot, id, target, args, full_msg):
    try:
        mod = sys.modules[args]
        if hasattr(mod, 'uninstall'):
            # uninstall may raise a KeyError if the module is not installed.
            try: mod.uninstall(bot)
            except KeyError: pass
        deep_reload(mod)
        if hasattr(mod, 'install'): mod.install(bot)
        echo(bot, id, target, 'Done.')
    except KeyError as e:
        echo(bot, id, target, repr(e))
