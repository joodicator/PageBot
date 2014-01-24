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
    ' used by channel operators, and if the bot is itself a channel operator.')

@link('!topic-replace')
def h_topic_replace(bot, id, target, args, full_msg):
    if not target: return

    match = re.match(r'\s*"((?:\\.|[^"])*)"\s*"((?:\\.|[^"])*)"\s*$', args)
    if not match:
        reply(bot, id, target, 'Error: two double-quoted strings expected.')
        return
    find_str = match.group(1).replace('\\"', '"')
    repl_str = match.group(2).replace('\\"', '"')

    if not find_str:
        reply(bot, id, target, 'Error: string to replace may not be empty.')
        return

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
    new_topic = topic.replace(find_str, repl_str)
    if new_topic == topic:
        reply(bot, id, target, 'Topic is unchanged.')
    elif len(new_topic) > 500:
        reply(bot, id, target, 'Error: New topic would be too long.')
    else:
        bot.send_cmd('TOPIC %s :%s' % (target, new_topic))
