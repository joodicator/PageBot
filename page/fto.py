import re
import util
import message

link, install, uninstall = util.LinkSet().triple()

cooldown = False

@link(('MESSAGE', '#page'))
def h_message_fto(bot, id, target, msg):
    if strip('joujou yuujou! banji maji kaichou!') in strip(msg):
        reply = 'Nanananananana!'
        message.reply(bot, id, target, reply, prefix=False)

def strip(text):
    return re.sub(r'[^a-z]', '', text.lower())
