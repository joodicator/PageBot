from __future__ import print_function

import sys
import traceback
import urllib
import urllib2
import json
import re

from bs4 import BeautifulSoup
from untwisted.magic import sign

import util
import runtime
import identity

STATE_FILE = 'state/qdbs.json'
CONF_FILE = 'conf/qdbs.py'
TICK_PERIOD_S = 60

link = util.LinkSet()
def install(bot):
    link.install(bot)
    bot.drive('QDBS_TICK', bot, log_level=2)
install, uninstall = util.depend(install, link.uninstall, 'identity')

#===============================================================================
def read_conf():
    try:
        return util.table(CONF_FILE, 'qdbs_conf_entry')
    except IOError as e:
        if e.errno != 2: raise
    except:
        traceback.print_exc()
    return dict()

def read_state():
    try:
        with open(STATE_FILE, 'r') as file:
            return json.load(file)
    except IOError as e:
        if e.errno != 2: raise
    except:
        traceback.print_exc()
    return dict()

def write_state(wstate):
    with open(STATE_FILE, 'w') as file:
        json.dump(wstate, file)

conf = read_conf()
state = read_state()

#===============================================================================
@link('QDBS_TICK')
def h_qdbs_tick(bot, log_level=None):
    for entry in conf:
        yield refresh_conf_entry(bot, entry)
    yield runtime.sleep(TICK_PERIOD_S)
    yield sign('QDBS_TICK', bot, log_level=log_level)

@util.msub(link, 'qdbs.refresh_conf_entry')
def refresh_conf_entry(bot, entry):
    try:
        nicks = yield identity.enum_access(bot, entry.access_name)
        if not nicks: return
        quotes = conf_entry_quotes(entry)
        for nick in nicks:
            url_state = state.get(entry.admin_url, {})
            name_state = url_state.get(entry.access_name.lower(), {})
            last_quote = name_state.get('last_quote')

            for qid, quote in sorted(quotes):
                if qid > last_quote:
                    quote = quote.encode('utf-8')
                    msg = '[QdbS] New quote #%d: %r' % (qid, quote)
                    bot.send_msg(nick, msg)

            last_quote = max(last_quote, max(qid for (qid, quote) in quotes))
            name_state['last_quote'] = last_quote
            url_state[entry.access_name.lower()] = name_state
            state[entry.admin_url] = url_state
            write_state(state)
    except:
        traceback.print_exc()

def conf_entry_quotes(entry):
    quotes = []
    soup = conf_entry_soup(entry)
    add_quotes = soup.find_all('a', {'title': 'Add Quote'})
    if add_quotes:
        for add_quote in add_quotes:
            qid = int(re.search(r'q=(\d+)', add_quote.get('href')).group(1))
            body = add_quote.find_parent('table').find('td', {'class': 'body'})
            quotes.append((qid, body.text.strip()))
    else:
        for tag in soup.find_all('td', {'class': 'title'}):
            if tag.text.strip() == 'There are no new quotes!':
                break
        else:
            print(soup.encode('utf-8'), file=sys.stderr)
            raise Exception('Unexpected QdbS admin page format.')   
    return quotes

def conf_entry_soup(entry):
    stream = urllib2.urlopen(urllib2.Request(entry.admin_url, headers={
        'Cookie': 'qdb_username=%s; qdb_password=%s' % (
            entry.qdb_username, entry.qdb_password)}))
    encoding = stream.info().getparam('charset')
    return BeautifulSoup(stream, 'html5lib', from_encoding=encoding)
