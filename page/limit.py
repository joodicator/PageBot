from util import message_reply as reply
import time

FLOOD_COUNT_PERIOD  = 5     # If during a period of 5 seconds,
FLOOD_COUNT_LIMIT   = 5     # more than 5 commands are sent,
FLOOD_IGNORE_PERIOD = 150   # ignore the user for 2.5-5 minutes.

flood_count_start = None    # Start of current FLOOD_COUNT_PERIOD.
flood_count = dict()        # Command count for each user@host.

flood_ignore_start = None   # Start of current FLOOD_IGNORE_PERIOD.
flood_ignore_new = set()    # ignored IDs from current period.
flood_ignore_old = set()    # ignored IDs from previous period.
flood_ignore_notify = set() # ignored IDs who have been notified.

#===============================================================================
# Signal that `id' has issued a single command to the bot, or otherwise
# performed an action deemed to be subject to flood-protection.
#
# If flooding is detected and the command should be ignored, returns True;
# otherwise, returns False.
#
# If `notify' is given and is not False, and the user has not already been
# notified of this since they became ignored, then the user is notified that they
# have been ignored, in the given channel (or by PM, if `notify' is None).
def mark_activity(bot, id, notify=False):
    global flood_count_start
    global flood_ignore_start
    global flood_ignore_notify

    now = time.time()
    userhost = (id.user, id.host)

    if flood_count_start is None \
    or now > flood_count_start + FLOOD_COUNT_PERIOD:
        flood_count.clear()
        flood_count_start = now

    if flood_ignore_start \
    and now > flood_ignore_start + 2*FLOOD_IGNORE_PERIOD:
        flood_ignore_new.clear()

    if flood_ignore_start is None \
    or now > flood_ignore_start + FLOOD_IGNORE_PERIOD:
        flood_ignore_old.clear()
        flood_ignore_old.update(flood_ignore_new)
        flood_ignore_new.clear()        
        flood_ignore_notify &= flood_ignore_old | flood_ignore_new
        flood_ignore_start = now
    
    flood_count[userhost] = flood_count.get(userhost, 0) + 1
    if flood_count[userhost] > FLOOD_COUNT_LIMIT:
        flood_ignore_new.add(userhost)

    if userhost in flood_ignore_new or userhost in flood_ignore_old:
        if notify != False and userhost not in flood_ignore_notify:
            reply(bot, id, notify,
                'You have been ignored for sending commands too quickly.')
            flood_ignore_notify.add(userhost)       
        return True
    else:
        return False

def is_ignored(id):
    userhost = (id.user, id.host)
    return userhost in flood_ignore_new \
        or userhost in flood_ignore_old
