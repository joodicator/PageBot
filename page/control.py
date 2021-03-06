from __future__ import print_function

from importlib import import_module
import traceback
import sys
import re

from untwisted.magic import sign
from untwisted.usual import Stop

from util import LinkSet, AlreadyInstalled, NotInstalled
from message import reply as echo
from auth import admin
import util
import auth

link, install, uninstall = LinkSet().triple()
install, uninstall = util.depend(install, uninstall,
    'auth')

@link('!echo')
@admin
def _echo(bot, id, target, args, full_msg):
    echo(bot, id, target, args, False)

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
    bot.send_msg(match.group('whom'), '\1ACTION ' + match.group('msg') + '\1')

@link('!j')
@link('!join')
@admin
def _join(bot, id, target, args, full_msg):
    bot.send_cmd('JOIN :%s' % args)

@link('!part')
@admin
def _part(bot, id, target, args, full_msg):
    bot.send_cmd('PART :%s' % (args or target))

@link('!quit')
@admin
def _quit(bot, id, target, args, full_msg):
    bot.send_cmd('QUIT :%s' % args if args else 'QUIT')

@link('!restart')
@admin
def _restart(bot, id, target, args, full_msg):
    bot.send_cmd('QUIT :Restarting.')

@link('!eval')
@admin
def _eval(bot, id, target, args, full_msg):
    try:
        result = eval(args, sys.modules, {'bot':bot})
    except Exception as e:
        traceback.print_exc()
        result = e
    echo(bot, id, target, repr(result))

@link('!exec')
@admin
def _exec(bot, id, target, args, full_msg):
    try:
        exec args in sys.modules, {'bot':bot}
    except Exception as e:
        traceback.print_exc()
        echo(bot, id, target, repr(e))

@link('!yield')
@admin
@util.multi('!yield')
def _mcall(bot, id, target, args, full_msg, reply):
    try:
        result = yield eval(args, sys.modules, {'bot':bot})
    except Exception as e:
        result = e
    reply(repr(result))

@link('!load')
@admin
def _load(bot, id, target, args, full_msg):
    try:
        mod = import_module(args)
        if hasattr(mod, 'install'): mod.install(bot)
        echo(bot, id, target, 'Done.')
    except Exception as e:
        echo(bot, id, target, repr(e))
        traceback.print_exc()

@link('!unload')
@admin
def _unload(bot, id, target, args, full_msg):
    try:
        mod = sys.modules[args]
        if hasattr(mod, 'uninstall'): mod.uninstall(bot)
        del sys.modules[args]
    except Exception as e:
        echo(bot, id, target, repr(e))
        traceback.print_exc()
    echo(bot, id, target, 'Done.')

@link('!reload')
@admin
def h_soft_reload(bot, id, target, args, full_msg):
    return h_reload(bot, id, target, hard=False)

@link('!hard-reload')
@admin
def h_hard_reload(bot, id, target, args, full_msg):
    return h_reload(bot, id, target, hard=True)

def h_reload(bot, id, target, hard):
    plugins = bot.conf['plugins']
    def order(m):
        name = m.__name__
        if name in plugins: return plugins.index(name)
        return len(plugins)

    local = filter(util.module_is_local, sys.modules.values())
    local.sort(key=order)
    names = [m.__name__ for m in local]
    
    old_modules = dict()
    expns = dict()

    # Uninstall all local modules (see util.module_is_local for definition).
    for module in reversed(local):
        try:
            if not hard and hasattr(module, 'reload_uninstall'):
                module.reload_uninstall(bot)
            elif hard and hasattr(module, 'hard_reload_uninstall'):
                module.hard_reload_uninstall(bot)
            elif hasattr(module, 'uninstall'):
                module.uninstall(bot)
        except NotInstalled:
            names.remove(module.__name__)
        except Exception as e:
            expns[module.__name__] = e
            traceback.print_exc()
        else:
            old_modules[module.__name__] = module
        del sys.modules[module.__name__]
    if expns:
        echo(bot, id, target, 'Errors during uninstall: ' + repr(expns))
        expns.clear()

    # Reinstall all uninstalled modules.
    for name in names:
        try:
            module = import_module(name)
            if name not in old_modules: continue
            if hasattr(module, 'reload') and not hard:
                module.reload(old_modules[name])
            elif hasattr(module, 'hard_reload') and hard:
                module.hard_reload(old_modules[name])
            if hasattr(module, 'install'):
                try:
                    module.install(bot)
                except AlreadyInstalled:
                    pass
        except Exception as e:
            expns[name] = e
            traceback.print_exc()
    if expns:
        for name in expns:
            if name in old_modules and hasattr(old_modules[name], 'uninstall'):
                try: old_modules[name].uninstall(bot)
                except NotInstalled: pass
                except: traceback.print_exc()
        echo(bot, id, target, 'Errors during reinstall: ' + repr(expns))

    yield sign('POST_RELOAD', bot)
    echo(bot, id, target, 'Reload complete.')

    raise Stop
