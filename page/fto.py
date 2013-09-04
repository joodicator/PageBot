import re
import util
import message

link, install, uninstall = util.LinkSet().triple()

@link(('MESSAGE', '#fto'))
def h_message_fto(bot, id, target, msg):
    na = 'Nanananananana!'
    if (strip('joujou yuujou! banji maji kaichou!') in strip(msg)
    and strip(na) not in strip(msg)):
        message.reply(bot, id, target, na, prefix=False)

def strip(text):
    return re.sub(r'[^a-z]', '', text.lower())
