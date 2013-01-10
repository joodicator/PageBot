from importlib import import_module
from util import LinkSet
import util
from auth import admin
import sys
import re

link, install, uninstall = LinkSet().triple()

def echo(bot, id, target, args):
    if target:
        bot.send_msg(target, '%s: %s' % (id.nick, args))
    else:
        bot.send_msg(id.nick, args)

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

@link('!act')
@admin
def _act(bot, id, target, args, full_msg):
    match = re.match('(?P<whom>\S*)\s*(?P<msg>.*)$', args)
    bot.send_msg(match.group('whom'), '\1ACTION ' + match.group('msg'))

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
        del sys.modules[args]
    except KeyError as e:
        echo(bot, id, target, repr(e))
    echo(bot, id, target, 'Done.')

@link('!reload')
@admin
def _reload(bot, id, target, args, full_msg):
    expns = dict()
    local = filter(util.module_is_local, sys.modules.values())
    names = [m.__name__ for m in local]
    echo(bot, id, target, 'Reloading: ' + repr(names))
    
    # Uninstall all local modules (see util.module_is_local for definition).
    for module in local:
        if hasattr(module, 'uninstall'):
            try:
                module.uninstall(bot)
            except Exception as e:
                expns[module.__name__] = e
        del sys.modules[module.__name__]
    if expns:
        echo(bot, id, target, 'Errors during uninstall: ' + repr(expns))
        expns.clear()
    
    # Reinstall all uninstalled modules.
    for name in names:
        try:
            module = import_module(name)
            if hasattr(module, 'install'): module.install(bot)
        except Exception as e:
            expns[name] = e
    if expns:
        echo(bot, id, target, 'Errors during reinstall: ' + repr(expns))

    echo(bot, id, target, 'Reload complete.')
