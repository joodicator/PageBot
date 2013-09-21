from untwisted.magic import sign, hold

import re
import time

import auth
import util
import message
link, install, uninstall = util.LinkSet().triple()

#===============================================================================
@link(('MESSAGE', '#fto'))
def h_message(bot, id, target, msg):
    yield sign('FTO_MSG', bot, id, target, msg)

@link(('MESSAGE', None))
@link(('MESSAGE', '#page'))
@auth.admin
def h_message_admin(bot, id, target, msg):
    yield sign('FTO_MSG', bot, id, target, msg)

#===============================================================================
@link('FTO_MSG')
def h_fto_msg(bot, id, target, msg):
    reply = lambda rmsg: message.reply(bot, id, target, rmsg, prefix=False)

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=kZn7i9rg3a0
    if strip('joujou yuujou! banji maji kaichou!') in strip(msg) \
    and strip('nanananana') not in strip(msg):
        reply('Nanananananana!')

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=Kxp8qPEwSXM
    elif strip('I am mighty Agamemnon!') in strip(msg) \
    and strip('Legolambnon') not in strip(msg):
        reply('I am tasty Legolambnon!')
    
    elif strip('I am King Agamemnon!') in strip(msg) \
    and strip('Legolambnon') not in strip(msg):
        reply('La la la la la la la la la Legolambnon!')
    
    elif strip('I command all of the Argives!') in strip(msg) \
    and strip('roast me up') not in strip(msg) \
    and strip('gas mark five') not in strip(msg):
        reply('Roast me up at gas mark five!')
    
    elif strip('I command man-killer Achilles!') in strip(msg) \
    and strip('with some peas') not in strip(msg):
        reply('Why not have me with some peas?')

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=1jJsYbVBnaE
    elif strip('me wanna you wanna everybody wanna') in strip(msg) \
    and strip('go go') not in strip(msg):
        reply('Go! Go! Go!')

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=WqacyIaq27o
    elif strip('DRIVE HARD.') == strip(msg):
        reply('DRIVE MUSTANG.')

    elif strip('DRIVE HARD') in strip(msg) \
    and strip('DRIVE MUSTANG') in strip(msg):
        reply('Why are you doing this?')

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=ogTDa-vG2MQ
    elif strip('You go, my lad!') == strip(msg) \
    or strip('Below, my lad!') == strip(msg):
        reply('Ho, ho! my lad!')

    #---------------------------------------------------------------------------
    # http://www.youtube.com/watch?v=8N_tupPBtWQ
    elif re.match(r'(doo+[dt]?){4}', strip(msg)) \
    and strip('mana') not in msg and strip('mahna') not in msg:
        reply('Mahna mahna!')

    #---------------------------------------------------------------------------
    # http://splicd.com/U-BwZA70ZCI/168/190
    elif strip('Banana! Banana!') in strip(msg):
        remaining = map(strip, 
        'BananaBanana Cucumber Eggplant Caviar Papaya GIANTASPARAGUS'.split())
        start = time.clock()
        while True:
            part = ''
            while remaining and part + remaining[0] in strip(msg):
                part += remaining.pop(0)

            if len(remaining) <= 1: break

            (_, (bot, id, target, msg)) = yield hold(bot, 'FTO_MSG')
            if strip('Banana! Banana!') in strip(msg): return
            if time.clock() - start > 3600: return

        if remaining: reply('\2GIANT ASPARAGUS!')

#===============================================================================
def strip(text):
    return cstrip(text.lower())

def cstrip(text):
    return re.sub(r'[^a-z]', '', text, flags=re.I)