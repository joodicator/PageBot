from importlib import import_module
import traceback
import sys
import re

from util import LinkSet, AlreadyInstalled, NotInstalled
from message import reply as echo
from auth import admin
import util
import auth

link, link_install, uninstall = LinkSet().triple()

def install(bot):
    for dep in 'auth',:
        try: __import__(dep).install(bot)
        except AlreadyInstalled: pass
    link_install(bot)

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
        result = eval(args, sys.modules, {'bot':bot})
    except Exception as e:
        result = e
    echo(bot, id, target, repr(result))

@link('!exec')
@admin
def _exec(bot, id, target, args, full_msg):
    try:
        exec args in sys.modules, {'bot':bot}
    except Exception as e:
        echo(bot, id, target, repr(e))

@link('!yield')
@admin
def _mcall(bot, id, target, args, full_msg):
    try:
        result = yield eval(args, sys.modules, {'bot':bot})
    except Exception as e:
        result = e
    echo(bot, id, target, repr(result))

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
    h_reload(bot, id, target, hard=False)

@link('!hard-reload')
@admin
def h_hard_reload(bot, id, target, args, full_msg):
    h_reload(bot, id, target, hard=True)

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
        if hasattr(module, 'uninstall'):
            try:
                if not hard and hasattr(module, 'reload_uninstall'):
                    module.reload_uninstall(bot)
                else:
                    try: module.uninstall(bot)
                    except NotInstalled: pass
                    except sys.modules['util'].NotInstalled: pass
                old_modules[module.__name__] = module
            except Exception as e:
                expns[module.__name__] = e
                traceback.print_exc()
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
            if hasattr(module, 'install'):
                try: module.install(bot)
                except AlreadyInstalled: pass
                except sys.modules['util'].AlreadyInstalled: pass
        except Exception as e:
            expns[name] = e
            traceback.print_exc()
    if expns:
        echo(bot, id, target, 'Errors during reinstall: ' + repr(expns))

    echo(bot, id, target, 'Reload complete.')
