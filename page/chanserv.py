import channel
import util

import re

link, l_install, uninstall = util.LinkSet().triple()

EVICT_FILE      = 'conf/chanserv_evict.txt'
PASSWORD_FILE   = 'conf/chanserv_password.py'

def install(bot):
    l_install(bot)
    for chan in channel.track_channels.iterkeys():
        evict_chanserv(bot, chan)

@link('OTHER_JOIN')
def h_other_join(bot, id, chan):
    evict_chanserv(bot, chan)

@link('NAMES')
def h_names(bot, chan, *args):
    evict_chanserv(bot, chan)

def evict_chanserv(bot, chan):
    try:
        with open(EVICT_FILE) as file:
            evict_channels = re.findall(r'\S+', file.read())
    except IOError:
        return
    if chan not in evict_channels: return

    names = map(str.lower, channel.track_channels[chan])
    if 'ChanServ'.lower() not in names: return

    records = util.table(PASSWORD_FILE)
    for r in [r for r in records if r.channel.lower() == chan]:
        bot.send_msg('ChanServ', 'IDENTIFY %s %s' % (chan, r.password))
        bot.send_msg('ChanServ', 'PART %s' % chan)
