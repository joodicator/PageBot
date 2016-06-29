# coding: utf8

from untwisted.magic import sign, hold

import re
import time

from channel import not_quiet
import message
import channel
import runtime
import util
import limit

link, install, uninstall = util.LinkSet().triple()

#===============================================================================
@link('MESSAGE')
@not_quiet()
def h_message(bot, id, target, msg):
    if not target: return
    if limit.is_ignored(id): return
    yield sign('FTO_MSG', bot, id, target, msg)
    if bot.activity: limit.mark_activity(bot, id)

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

    elif strip('I sailed to troy with the navy!') in strip(msg) \
    and not re.search(r'taste great|spuds|gravy', sstrip(msg)):
        reply('I taste great with spuds and gravy!')
    
    elif strip('I am King Agamemnon!') in strip(msg) \
    and strip('Legolambnon') not in strip(msg):
        reply('La la la la la la la la la Legolambnon!')
    
    elif strip('I command all of the Argives!') in strip(msg) \
    and strip('roast me up') not in strip(msg) \
    and strip('gas mark five') not in strip(msg):
        reply('Roast me up at gas mark five!')
    
    elif strip('All Achaeans bow to me!') in strip(msg) \
    and strip('rosemary') not in strip(msg):
        reply('I taste great with rosemary-hee!')

    elif strip('I command man-killer Achilles!') in strip(msg) \
    and strip('with some peas') not in strip(msg):
        reply('Why not have me with some peas?')

    elif strip('I spill entrails of our Trojan foe!') in strip(msg) \
    and not re.search(r'nice with|garlic|dont you know', sstrip(msg)):
        reply("I'm nice with garlic, don't you know?")

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
            while True:
                _, (e_bot, e_id, e_target, msg) = yield hold(bot, 'FTO_MSG')
                if e_target and e_target.lower() == target.lower(): break
            if time.clock() - start > 3600: return
            if strip('Banana! Banana!') in strip(msg): return

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
            (_, (e_bot, e_id, e_target, msg)) = yield hold(bot, 'FTO_MSG')
            if not e_target or e_target.lower() != target.lower():
                continue
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

    elif re.search(r'(ya|you(ve)?)seen?onecrowdedpollutedstinking?town',
    strip(msg)):
        reply('Tea, girls, warm and sweet (warm! sweet!),'
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
    elif re.match(r'se+no', strip(msg)):
        write = [
            ('Se~ no',
            r'se+no'),
            ('Demo sonnanja dame',
            r'demosonn?anjadame'),
            ('Mou sonnanja hora~',
            r'mou?sonn?anjahora'),
            ('Kokoro wa shinka suru yo motto motto~',
            r'kokorowashinkasuruyomott?omott?o')]
        read = ''
        smsg = strip(msg)
        while write and re.match(read + write[0][1], smsg):
            read += write.pop(0)[1]
        if not re.match(read + r'$', smsg):
            return
        for line in write:
            reply(line[0])
            yield runtime.sleep(1)

    #---------------------------------------------------------------------------
    # The Fellowship of the Ring (2001) - The Council of Elrond
    # https://www.youtube.com/watch?v=pxPGzj2L3n0
    elif re.search(r'^(you have|and) my \S+'
    '|(you have|and) my \S+( \S+)?$', sstrip(msg)):
        global and_my_axe
        try:
            if time.time() < and_my_axe.get(target.lower()): return
        except NameError:
            and_my_axe = dict()
        and_my_axe[target.lower()] = time.time() + 60

        while time.time() < and_my_axe[target.lower()]:
            _, (e_bot, e_id, e_target, e_msg) = yield hold(bot, 'FTO_MSG')
            if not e_target or e_target.lower() != target.lower():
                continue
            if re.search(r'^and( you have)? my \S+'
            '|and( you have)? my \S+( \S+)?$', sstrip(e_msg)):
                reply('AND MY AXE!')
                break

    #---------------------------------------------------------------------------
    # Blackout Crew - Put A Donk On It
    # https://www.youtube.com/watch?v=ckMvj1piK58
    elif re.search('you know what you (wanna|want to) do with that( right)?$',
    sstrip(msg)) and not re.search(r'put a|banging|donk', sstrip(msg)):
        reply('You wanna put a \2banging donk\2 on it!')

    elif strip(msg) == strip('Bassline!'):
        reply('Aw, wicked! Now put a donk on it!')

    elif strip(msg) == strip('Electro!'):
        reply("Ah thats sick that m8! Put a donk on it!")

    elif strip(msg) == strip('Techno!'):
        reply("Aw, now that is good! Put a donk on it!")

    #---------------------------------------------------------------------------
    # Excel Saga, Episode 3 - Nabeshin's "No Escape"
    # https://www.youtube.com/watch?v=tORRPhqu1Co
    elif strip('Where are we going, general?') in strip(msg) and \
    not re.search(r'dont have|special (reason|raisin)', sstrip(msg)):
        reply("Who cares? We don't have a special raisin!")

    elif sstrip(msg).endswith(sstrip('Then why should we fly?')) and \
    not re.search(r'its just for|direction|low budget movie', sstrip(msg)):
        reply("It's just for the direction of low-budget movie.")

    #---------------------------------------------------------------------------
    # Repo! The Genetic Opera - Zydrate Anatomy
    # https://www.youtube.com/watch?v=aVTAf4FAXaU
    elif sstrip(msg).endswith(' a little glass vial') and \
    len(re.findall(r'alittleglassvial', strip(msg))) == 1:
        reply('A little glass vial?')
    
    elif (sstrip(msg).endswith(' into the gun like a battery') or \
    re.search(r'against(your|my|his|her|their|its)anatomy$', strip(msg))) \
    and not re.search(r'\b([ah]{2,} [ah]{2,})\b', sstrip(msg)):
        reply('Hah~ hah~')

    elif (sstrip(msg).endswith(' ready for surgery') or \
    sstrip(msg).endswith(' surgery') and re.search(r' S\S+$', csstrip(msg)) and \
    len(re.findall(r'\b[A-Z]\S+', msg)) < len(re.findall(r'\b[a-z]\S+', msg))) \
    and len(re.findall(r'\bsurgery\b', sstrip(msg))) == 1:
        reply('Surgery!')

    elif sstrip(msg).endswith(' addicted to the knife') and \
    len(re.findall(r'addictedtotheknife', strip(msg))) == 1:
        reply('Addicted to the knife?')

    elif sstrip(msg).endswith(' a little help with the agony') and \
    len(re.findall(r'agony', strip(msg))) == 1:
        reply('Agony~')

    elif re.search(r'\b(its clear)\b', sstrip(msg)):
        end_time = time.time() + 300
        remain = ["it's clear", "it's pure", "it's rare"]
        while remain:
            if strip('takes you there') in strip(msg): return
            rstr = r'^.*?\b(%s)\b' % re.escape(sstrip(remain[0]))
            sub_msg = re.sub(rstr, '', sstrip(msg))
            if sub_msg != sstrip(msg):
                del remain[0]
                msg = sub_msg
            else:
                e_target = ''
                while e_target.lower() != target.lower():
                    _, (e_bot, e_id, e_target, msg) = yield hold(bot, 'FTO_MSG')
                    if time.time() > end_time: return
                if re.search(r'\b(its clear)\b', sstrip(msg)): return
                bot.activity = True
        else:
            reply('It takes you there~')

    #---------------------------------------------------------------------------
    # Azumanga Daioh, Episode 21 - Saataa Andaagii
    # https://www.youtube.com/watch?v=b6swokLgCcU
    elif re.search(r'sa+ta+ a+nda+gi+', sstrip(msg)):
        global saataa_andaagii
        try:
            if time.time() < saataa_andaagii.get(target.lower()): return
        except NameError:
            saataa_andaagii = dict()
        saataa_andaagii[target.lower()] = time.time() + 300

        count = 1
        while count < 3:
            if time.time() > saataa_andaagii.get(target.lower()): break
            _, (e_bot, e_id, e_target, e_msg) = yield hold(bot, 'FTO_MSG')
            if e_target.lower() != target.lower(): continue
            if not re.search(r'sa+ta+ a+nda+gi+', sstrip(e_msg)): continue
            count += 1
            bot.activity = True
        else:
            reply('\2Saataa andaagii!')

    #---------------------------------------------------------------------------
    # 1-800-CONTACTS TV Advert - "Overly Dramatic Dramatization"
    # https://www.youtube.com/watch?v=f9YBwa0O1Zc
    elif ('your contact lenses just arrived' in sstrip(msg)
    and 'my brand' not in sstrip(msg) and 'special eyes' not in sstrip(msg)):
        reply("1-800-CONTACTS? They can't have my brand! I have special eyes...")
    elif ('look with your special eyes' in sstrip(msg)
    and 'my brand' not in sstrip(msg)):
        reply("My brand!")

#===============================================================================
@link('!nuke')
def h_nuke(bot, id, target, args, full_msg):
    if not target: return
    if not channel.has_op_in(bot, bot.nick, target, 'h'): return

    global nuclear_launch
    target_id = (target.lower(), ('%s!%s@%s' % id).lower())
    try:
        if target_id in nuclear_launch: return
    except NameError:
        nuclear_launch = set()
    nuclear_launch.add(target_id)

    message.reply(bot, id, target, 'Nuclear launch detected.', prefix=False)
    yield runtime.sleep(15)
    bot.send_cmd('KICK %s %s :GIANT ASPARAGUS!' % (target, id.nick))
    
    ERR_CHANOPRIVSNEEDED = '482'
    UNREAL_ERR_CANNOTDOCOMMAND = '972'
    timeout = yield runtime.timeout(10)
    while True:
        event, args = yield hold(bot, timeout,
            UNREAL_ERR_CANNOTDOCOMMAND, ERR_CHANOPRIVSNEEDED)
        if event == UNREAL_ERR_CANNOTDOCOMMAND:
            e_bot, e_src, e_tgt, e_cmd, e_args = args
            if e_cmd.upper() != 'KICK': continue
            message.reply(bot, id, target,
                'Nuclear launch failed: "%s".' % e_args, prefix=False)
        elif event == ERR_CHANOPRIVSNEEDED:
            e_bot, e_src, e_tgt, e_chan, e_args = args
            if e_chan.lower() != target.lower(): continue
            message.reply(bot, id, target,
                'Nuclear launch failed: "%s".' % e_args, prefix=False)
        elif event == timeout:
            break

    nuclear_launch.discard(target_id)

#===============================================================================
def strip(text):
    return cstrip(text.lower())

def cstrip(text):
    return re.sub(r'[^a-zA-Z]', '', text)

def sstrip(text):
    return csstrip(text.lower())

def csstrip(text):
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^\s+|\s+$', '', text)
    return text
