import untwisted.event
from control import NotInstalled

def install(bot, no_numeric=False):
    old_drive = bot.drive
    def drive(event, *args):
        if event == untwisted.event.TICK: return
        if event == untwisted.event.READ: return
        if event == untwisted.event.WRITE: return
        if type(event) == int:
            if no_numeric: return
            event = numeric(event)
        else:
            event = repr(event)

        if hasattr(bot, 'domain'):
            domain = bot.domain
        else:
            domain = id(bot)

        print '@%s %s %s' % (domain, event, args)

    def new_drive(event, *args):
        drive(event, *args)
        old_drive(event, *args)
    bot.drive = new_drive

    def uninstall():
        del bot.drive
        if not hasattr(bot, 'drive') or bot.drive != old_drive:
            bot.drive = old_drive
        del bot._debug_uninstall
    bot._debug_uninstall = uninstall

def uninstall(bot):
    if hasattr(bot, '_debug_uninstall'):
        bot._debug_uninstall()
    else:
        raise NotInstalled

def numeric(event):
    for name, number in untwisted.event.__dict__.iteritems():
        if event == number and name.upper() == name: return name
    return event
