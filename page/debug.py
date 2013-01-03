def install(bot):
    old_drive = bot.drive
    def drive(event, *args):
        if type(event) != int:
            print '@ %s %s' % (event, args)
        old_drive(event, *args)
    bot.drive = drive
    def uninstall():
        del bot.drive
        if not hasattr(bot, 'drive') or bot.drive != old_drive:
            bot.drive = old_drive
        del bot._debug_uninstall
    bot._debug_uninstall = uninstall

def uninstall(bot):
    bot._debug_uninstall()
