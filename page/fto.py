# coding: utf8

from untwisted.magic import sign, hold

import re
import time

from channel import not_quiet
import message
import channel
import runtime
import util

link, install, uninstall = util.LinkSet().triple()

#===============================================================================
@link('MESSAGE')
@not_quiet()
def h_message(bot, id, target, msg):
    if not target: return
    yield sign('FTO_MSG', bot, id, target, msg)

#===============================================================================
@link('FTO_MSG')
def h_fto_msg(bot, id, target, msg):
    reply = lambda rmsg: message.reply(bot, id, target, rmsg, prefix=False)

    #---------------------------------------------------------------------------
    # Nichijou Opening 2
    # http://www.youtube.com/watch?v=kZn7i9rg3a0
    if strip('joujou yuujou! banji maji kaichou!') in strip(msg) \
    and strip('nanananana') not in strip(msg):
        reply('Nanananananana!')

    #---------------------------------------------------------------------------
    # Rathergoodstuff - Agamemnon
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

    elif strip('All Achaeans bow to me!') in strip(msg) \
    and strip('rosemary') not in strip(msg):
        reply('I taste great with rosemary-hee!')

    #---------------------------------------------------------------------------
    # 【MMD】With pleasant companions『Go!Go!Carlito!』【PV】
    # http://www.youtube.com/watch?v=1jJsYbVBnaE
    elif strip('me wanna you wanna everybody wanna') in strip(msg) \
    and strip('go go') not in strip(msg):
        reply('\2Go! Go! Go!')

    elif re.search(r'whos(the|that)boy(wanna|wantto)beamigo', strip(msg)) \
    and strip('Carlito') not in strip(msg):
        reply('\2Carlito! Carlito!')

    elif re.search(r'whos(the|that)boy(iwill|ill)neverletgo', strip(msg)) \
    and strip('Carlito') not in strip(msg):
        reply('\2Carli-Carlito! Carli-Carlito!')

    elif re.search(r'whos(the|that)boycomeanddanceamigo', strip(msg)) \
    and strip('Carlito') not in strip(msg):
        reply('\2Carlito! Carlito! Carli-Carlito!')

    elif re.search(r'whos(the|that)boytakeachanceonmenow', strip(msg)) \
    and not re.search(r'señorita|carlita', strip(msg)):
        reply(u'\2Eyy, Señorita, where you going? You wanna be my Carlita?!')

    elif re.search(r'icansingandicandanceia?mveryniceandhotandspicy', \
    strip(msg)) and not any(strip(s) in strip(msg) for s in [
    'I have the looks', 'cook a TACO']):
        reply('I have the looks and I can cook a TACO!')

    #---------------------------------------------------------------------------
    # Dark Souls: The Wrath of the Darkwraith
    # http://www.youtube.com/watch?v=WqacyIaq27o
    elif cstrip('DRIVE HARD.') == cstrip(msg):
        reply('DRIVE MUSTANG.')
    
    elif strip('Drive hard.') == strip(msg):
        reply('Drive Mustang.')

    elif strip('DRIVE HARD') in strip(msg) \
    and strip('DRIVE MUSTANG') in strip(msg):
        reply('Why are you doing this?')

    #---------------------------------------------------------------------------
    # The Hobbit (1977) - Down, Down to Goblin Town
    # http://www.youtube.com/watch?v=ogTDa-vG2MQ
    elif strip('You go, my lad!') == strip(msg) \
    or strip('Below, my lad!') == strip(msg):
        reply('Ho, ho! my lad!')

    #---------------------------------------------------------------------------
    # The Muppet Show - Mahna Mahna
    # http://www.youtube.com/watch?v=8N_tupPBtWQ
    elif re.match(r'(doo+[dt]?){4}', strip(msg)) \
    and strip('mana') not in msg and strip('mahna') not in msg:
        reply('Mahna mahna!')

    #---------------------------------------------------------------------------
    # Puni Puni Poemi, Episode 2
    # http://www.youtube.com/watch?v=U-BwZA70ZCI#t=168
    elif strip('Banana! Banana!') in strip(msg):
        remaining = map(strip, 
        'BananaBanana Cucumber Eggplant Caviar Papaya GIANTASPARAGUS'.split())
        start = time.clock()
        while True:
            part = ''
            while remaining and part + remaining[0] in strip(msg):
                part += remaining.pop(0)

            if len(remaining) <= 1: break

            bot.activity = True
            (_, (bot, id, target, msg)) = yield hold(bot, 'FTO_MSG')
            if strip('Banana! Banana!') in strip(msg): return
            if time.clock() - start > 3600: return

        if remaining: reply('\2GIANT ASPARAGUS!')

    #---------------------------------------------------------------------------
    # HEYYEYAAEYAAAEYAEYAA
    # http://www.youtube.com/watch?v=6GggY4TEYbk
    elif re.search(r'ands?hetries', strip(msg)) \
    and not any(strip(s) in strip(msg) for s in \
    ['Oh my god', 'do I try', 'I try all the time', 'in this institution']):
        reply('Oh my god, do I try!')
        yield runtime.sleep(1)
        reply('I try all the time... in this institution!')
    
    elif re.search(r'ands?heprays', strip(msg)) \
    and not any(strip(s) in strip(msg) for s in \
    ['Oh my god', 'do I pray', 'I pray every single day', 'REVOLUTION']) \
    and not re.search(r'[mn]y[ea]+', strip(msg)):
        reply('Oh my god, do I pray!')
        yield runtime.sleep(1)
        reply('I pray every single day...')
        start = time.clock()
        while time.clock() - start < 60:
            (_, (bot, id, target, msg)) = yield hold(bot, 'FTO_MSG')
            if strip('And he prays!') in strip(msg):
                return
            if re.search(r'[mn]y[ea]+', strip(msg)):
                reply('\2...FOR REVOLUTION!')
                return

    #---------------------------------------------------------------------------
    # Murray Head - One Night In Bangkok
    # http://www.youtube.com/watch?v=xqZCGTe5ISQ
    elif strip("One town's very like another"
    " when your head's down over your pieces, brother.") in strip(msg) \
    and not any(strip(s) in strip(msg) for s in ["It's a drag", "it's a bore",
    "it's really such a pity", "looking at the board", "looking at the city"]):
        reply("It's a drag, it's a bore, it's really such a pity"
        " to be looking at the board, not looking at the city!")

    elif re.search(r'you(ve)?seen?onecrowdedpollutedstinking?town', strip(msg)):
        reply('Tea girls, warm and sweet (warm! sweet!),'
        ' some are set up in the Somerset Maugham suite!')

    elif (strip("And if you're lucky then the god's a she") in strip(msg) 
    or strip("A little flesh, a little history") in strip(msg)) \
    and not any(strip(s) in strip(msg) for s in [
    'I can feel', 'an angel', 'sliding up to me']):
        reply('I can feel an angel sliding up to me~')

    elif strip("Can't be too careful with your company") in strip(msg) \
    and not any(strip(s) in strip(msg) for s in [
    'I can feel', 'the devil', 'walking next to me']):
        reply('I can feel the devil walking next to me~')

    elif strip("I don't see you guys rating the kind of mate I'm contemplating"
    ) in strip(msg) and not any(strip(s) in strip(msg) for s in [
    "I'd let you watch", "I would invite you", "the queens we use",
    "would not excite you"]):
        reply("I'd let you watch, I would invite you,"
        " but the queens \2we\2 use would not excite you.")

    #---------------------------------------------------------------------------
    # Hanazawa Kana - Renai Circulation
    # http://www.youtube.com/watch?v=lWTuzLz1C6o
    elif strip(msg).startswith(strip('Se~ no')):
        write = ['Se~ no', 'Demo sonnanja dame', 'Mou sonnanja hora~',
                 'Kokoro wa shinka suru yo motto motto~']
        read = ''
        smsg = strip(msg)
        while write and smsg.startswith(read + strip(write[0])):
            read += strip(write.pop(0))
        if smsg != read: return
        for line in write:
            reply(line)
            yield runtime.sleep(1)

#===============================================================================
def strip(text):
    return cstrip(text.lower())

def cstrip(text):
    return re.sub(r'[^a-z]', '', text, flags=re.I)
