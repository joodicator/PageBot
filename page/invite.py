import traceback
import os.path

import util

INVITE_FILE = 'state/channel_invite.txt'

link, install, uninstall = util.LinkSet().triple()
invited = set()

def reload(prev):
    try: invited.update(prev.invited)
    except: pass

@link('INVITE')
def h_invite(bot, id, target, channel, *args):
    if target.lower() != bot.nick.lower(): return
    invited.add(channel.lower())
    bot.send_cmd('JOIN %s' % channel)

@link('AUTOJOIN')
def h_autojoin(bot):
    if os.path.exists(INVITE_FILE):
        with open(INVITE_FILE) as file:
            file_invited = map(str.strip, file.readlines())
        for chan in file_invited:
            if chan.lower() in map(str.lower, bot.conf['channels']):
                continue
            bot.send_cmd('JOIN %s' % chan)

@link('SELF_JOIN')
def h_self_join(bot, chan):
    if chan.lower() not in invited:
        return
    if os.path.exists(INVITE_FILE):
        with open(INVITE_FILE) as file:
            for line in file:
                if chan.lower() == line.strip().lower():
                    return
    with open(INVITE_FILE, 'a') as file:
        file.write(chan + '\n')
    invited.remove(chan.lower())

@link('SELF_PART', 'SELF_KICKED')
def h_self_part_kicked(bot, chan, *args):
    if chan.lower() in invited:
        invited.remove(chan.lower())
    if os.path.exists(INVITE_FILE):
        with open(INVITE_FILE) as file:
            file_invited = map(str.strip, file.readlines())
        new_file_invited = filter(
            lambda c: c.lower() != chan.lower(), file_invited)
        if new_file_invited == file_invited: return
        with open(INVITE_FILE, 'w') as file:
            for c in new_file_invited: file.write(c + '\n')

