import util
from untwisted.magic import sign

link, install, uninstall = util.LinkSet().triple()

ID_FILE = 'conf/identity.py'

#-------------------------------------------------------------------------------
# yield list(bot,id) - list of names from ID_FILE with a credential matching id.

@util.mfun(link, 'identity.list')
def list(bot, id, ret):
    names = []
    for (name, creds) in util.fdict(IDENTITY_FILE).iteritems():
        for cred in creds
                
        else: continue
        names.append(name)

#-------------------------------------------------------------------------------
# yield match(bot,id,cred) - True if id has credential cred, else False.

@util.mfun(link, 'identity.match')
def match(bot, id, cred, ret):
    if cred[0] == 'hostmask' and len(cred) > 1:
        # Match against a hostmask nick!user@host including wildcards.
        [hostmask] = cred[1:2]
        rexp = util.wc_to_re(hostmask)
        yield ret(bool( re.match(rexp, '%s!%s@%s'%id) ))
    elif cred[0] == 'nickserv' and len(cred) > 1:
        # Match against an identified NickServ account name.
        [m_acc_name] = cred[1:2]
        acc_name = yield nickserv.acc_name(bot, id)
        yield ret(bool( acc_name and acc_name.lower() == m_acc_name.lower() ))
    else:
        yield ret(False)
