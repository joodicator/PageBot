# coding=utf8

import util

link, install, uninstall = util.LinkSet().triple()

@link('MESSAGE')
def h_message(bot, id, target, msg):
    if target is None: return
    if 'سمَـَّوُوُحخ ̷̴خ ̷̴خ ̷̴خ امارتيخ ̷̴خ' not in msg: return
    reason = 'for 1 day; do not abuse software exploits in this channel.'
    bot.send_msg('ChanServ', 'AKICK %s ADD *!*@%s !T 1d %s'
        % (target, id.host, reason))
