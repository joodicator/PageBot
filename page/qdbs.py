from __future__ import print_function

import sys
import traceback
import urllib
import urllib2
import json
import re
import UserDict

from bs4 import BeautifulSoup
from untwisted.magic import sign

import util
import runtime
import identity

STATE_FILE = 'state/qdbs.json'
BS4_PARSER = 'html5lib'
MAX_REPORT = 4
MAX_QUOTE_LEN = 300
TICK_PERIOD_S = 60

link = util.LinkSet()
def install(bot):
    link.install(bot)
    bot.drive('QDBS_TICK', bot, log_level=2)
install, uninstall = util.depend(install, link.uninstall, 'identity')

#===============================================================================
def read_state():
    try:
        with open(STATE_FILE, 'r') as file:
            return util.recursive_encode(json.load(file), 'utf-8')
    except IOError as e:
        if e.errno != 2: raise
    except:
        traceback.print_exc()
    return dict()

def write_state(wstate):
    data = json.dumps(wstate, indent=4, ensure_ascii=False)
    with open(STATE_FILE, 'w') as file:
        file.write(data)

state = read_state()

#===============================================================================
@link('QDBS_TICK')
def h_qdbs_tick(bot, log_level=None):
    yield Private.class_refresh(bot)
    yield Public.class_refresh(bot)
    yield runtime.sleep(TICK_PERIOD_S)
    yield sign('QDBS_TICK', bot, log_level=log_level)

def format_quote(quote):
    quote = re.sub(r'[\r\n]+', '  ', quote)
    if len(quote) > MAX_QUOTE_LEN:
        quote = quote[:MAX_QUOTE_LEN-5] + '(...)'
    return quote

#===============================================================================
class EmptyDict(UserDict.DictMixin):
    def __getitem__(self, key):
        raise KeyError
    def __delitem__(self, key):
        pass
    def __setitem__(self, key, val):
        pass

class Configuration(object):
    cache = EmptyDict()

    def __init__(self, raw_entry):
        for key, val in raw_entry.__dict__.iteritems():
            setattr(self, key, val)

    @classmethod
    def read_conf(cls):
        try:
            return util.table(cls.CONF_FILE, cls.__name__ + 'ConfEntry')
        except IOError as e:
            if e.errno != 2: raise
        except:
            traceback.print_exc()
        return dict()

    @classmethod
    def class_init(cls):
        cls.cache = dict()
        cls.entries = []
        for raw_entry in cls.read_conf():
            entry = cls(raw_entry)
            cls.entries.append(entry)

    @classmethod
    @util.msub(link, 'qdbs.Configuration.class_refresh')
    def class_refresh(cls, bot):
        cls.cache.clear()
        for entry in cls.entries:
            yield entry.refresh(bot)

#===============================================================================
class Private(Configuration):
    CONF_FILE = 'conf/qdbs_private.py'
    __slots__ = ('access_name', 'qdb_username', 'qdb_password', 'admin_url',
                 'remote_admin_url')

    @util.msub(link, 'qdbs.Private.refresh')
    def refresh(self, bot):
        try:
            quotes = self.quotes()
            if not quotes: return

            url_state = state.get(self.admin_url, {})
            name_state = url_state.get(self.access_name.lower(), {})
            last_quote = name_state.get('last_quote')
    
            nicks = yield identity.enum_access(bot, self.access_name)
            if not nicks: return

            for nick in nicks:
                for qid, quote in sorted(quotes):
                    if qid > last_quote:
                        fquote = format_quote(quote)
                        msg = '[QdbS] New quote #%d <%s>: "%s"' % (
                            qid, self.remote_admin_url, fquote)
                        if type(msg) is unicode:
                            msg = msg.encode('utf8')
                        bot.send_msg(nick, msg)
                        hm = yield identity.get_hostmask(bot, nick)
                        yield sign('PROXY_MSG', bot, None, hm, fquote, quiet=True)
    
            last_quote = max(
                last_quote, max(qid for (qid, quote) in quotes))
            name_state['last_quote'] = last_quote
            url_state[self.access_name.lower()] = name_state
            state[self.admin_url] = url_state
            write_state(state)
        except:
            traceback.print_exc()
    
    def quotes(self):
        if self.admin_url in self.cache:
            return self.cache[self.admin_url]
        
        quotes = []
        soup = self.soup()
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

        self.cache[self.admin_url] = quotes
        return quotes
    
    def soup(self):
        stream = urllib2.urlopen(urllib2.Request(self.admin_url, headers={
            'Cookie': 'qdb_username=%s; qdb_password=%s' % (
                self.qdb_username, self.qdb_password)}))
        encoding = stream.info().getparam('charset')
        return BeautifulSoup(stream, BS4_PARSER, from_encoding=encoding)

Private.class_init()

#===============================================================================
class Public(Configuration):
    CONF_FILE = 'conf/qdbs_public.py'
    __slots__ = ('channel', 'index_url', 'remote_index_url')

    @util.msub(link, 'qdbs.Public.refresh')
    def refresh(self, bot):
        try:
            quotes, title = self.quotes_title()
            url_state = state.get(self.index_url, {})
            chan_state = url_state.get(self.channel.lower(), {})
            last_quote = chan_state.get('last_quote')

            quotes = sorted(
                (qid, quote) for (qid, quote) in quotes if qid > last_quote)
            sample = quotes if len(quotes) <= MAX_REPORT else \
                     quotes[:MAX_REPORT-1]
            for qid, quote in sample:
                quote_url = '%s?%s' % (self.remote_index_url, qid)
                fquote = format_quote(quote)
                msg = '%s: new quote added: %s "%s"' % (title, quote_url, fquote)
                bot.send_msg(self.channel, msg)
                yield sign('PROXY_MSG', bot, None, self.channel, fquote, quiet=True)

            if len(quotes) > len(sample):
                msg = '%s: ...and %d others. See: <%s>.' % (
                    title, len(quotes)-len(sample), self.remote_index_url)
                bot.send_msg(self.channel, msg)

            if quotes:
                last_quote = max(
                    last_quote, max(qid for (qid, quote) in quotes))
                chan_state['last_quote'] = last_quote
                url_state[self.channel.lower()] = chan_state
                state[self.index_url] = url_state
                write_state(state)
        except:
            traceback.print_exc()

    def quotes_title(self):
        if self.index_url in self.cache:
            return self.cache[self.index_url]

        quotes = []
        soup = self.soup()

        heading = soup.find('td', {'class': 'heading'})
        if heading is None:
            print(soup.encode('utf-8'), file=sys.stderr)
            raise Exception('Unexpected QdbS index page format.')
        qdb_title = heading.text.strip()

        rate_links = soup.find_all('a', {'title': 'Rate as good'})
        for rate_link in rate_links:
            qid = int(re.search(r'q=(\d+)', rate_link.get('href')).group(1))
            body = rate_link.find_parent('table').find('td', {'class': 'body'})
            quotes.append((qid, body.text.strip()))

        self.cache[self.index_url] = quotes, qdb_title
        return quotes, qdb_title
    
    def soup(self):
        stream = urllib2.urlopen(self.index_url)
        encoding = stream.info().getparam('charset')
        return BeautifulSoup(stream, BS4_PARSER, from_encoding=encoding)

Public.class_init()
