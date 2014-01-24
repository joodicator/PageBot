import re

from untwisted.magic import hold

from message import reply
import channel
import util

link, install, uninstall = util.LinkSet().triple()

CHOP_MODES = '@%'


#===============================================================================
@link('HELP')
def h_help(bot, reply, args):
    reply('topic-replace "OLD" "NEW"',
    "Replaces OLD with NEW in the channel's topic.")

@link(('HELP', 'topic-replace'))
def h_help_topic_replace(bot, reply, args):
    reply('topic-replace "OLD" "NEW"',
    'Replaces every instance of the string OLD in the channel\'s topic with'
    ' NEW. The sequence \\" must be used in place of any double quote'
    ' characters in either string. If the channel has mode +t, may only be'
    ' used by channel operators, and if the bot is itself a channel operator.',
    'In addition, if just ^ or $ or * (without quotes) is given instead of'
    ' "OLD", then NEW will be, respectively, prepended or appended to the'
    ' topic (with no separator), or substituted for the whole topic.')

@link('!topic-replace')
def h_topic_replace(bot, id, target, args, full_msg):
    if not target: return

    match = re.match(r'\s*(?P<old>("(\\.|[^"])*"|\^|\$|\*))'
                     r'\s+(?P<new>"(\\.|[^"])*")\s*$', args)
    if not match:
        reply(bot, id, target,
        'Error: Invalid syntax. See "help topic-replace" for correct usage.')
        return
    old = match.group('old').replace('\\"', '"')
    new = match.group('new').replace('\\"', '"')

    if old == '""':
        reply(bot, id, target, 'Error: OLD string may not be empty.')
        return

    if old.startswith('\"') and old.endswith('\"'):
        old = re.escape(old[1:-1])
    else:
        old = old.replace('*', '.*')
    if new.startswith('\"') and new.endswith('\"'):
        new = new[1:-1].replace('\\', '\\\\')

    mode = yield channel.mode(bot, target)
    if re.search(r'\+[a-z]*t', mode[0]):
        names = yield channel.names(bot, target)
        names = map(str.lower, names)
        if not any(m+bot.nick.lower() in names for m in CHOP_MODES):
            reply(bot, id, target, 'Error: Unable to change topic.')
            return
        if not any(m+id.nick.lower() in names for m in CHOP_MODES):
            reply(bot, id, target, 'Access denied.')
            return

    topic = yield channel.topic(bot, target)
    new_topic = re.sub(old, new, topic)

    if new_topic == topic:
        reply(bot, id, target, 'Topic is unchanged.')
    elif len(new_topic) > 500:
        reply(bot, id, target, 'Error: New topic would be too long.')
    else:
        bot.send_cmd('TOPIC %s :%s' % (target, new_topic))
