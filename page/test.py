from auth import admin
from util import multi, LinkSet

link, install, uninstall = LinkSet().triple()

@link('!test')
@admin
@multi('!test', limit=3)
def h_test(bot, id, target, args, full_msg, reply):
    reply('[test:%s]' % args)
