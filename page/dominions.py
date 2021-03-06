from itertools import *
import traceback
import urllib2
import json
import time
import sys
import re
import os.path

from bs4 import BeautifulSoup

from untwisted.magic import sign
from util import recursive_encode
import channel
import runtime
import message
import util
import auth

STATE_FILE = 'state/dominions.json'
BS4_PARSER = 'html5lib'
UPDATE_PERIOD_S = 15
TICK_PERIOD_S = 15

PLAYED = re.compile(r'Turn played$')
UNFINISHED = re.compile(r'Turn (played but )?unfinished$')
ELIMINATED = re.compile(r'Eliminated$')
AI = re.compile(r'AI$')

#-------------------------------------------------------------------------------
link = util.LinkSet()
is_installed = False

def install(bot):
    global is_installed   
    link.install(bot)
    is_installed = True
    bot.drive('DOMINIONS_TICK', bot, log_level=2)

def uninstall(bot):
    global is_installed
    link.uninstall(bot)
    is_installed = False

install, uninstall = util.depend(install, uninstall,
    'auth', 'identity', 'channel')

#-------------------------------------------------------------------------------
class State(object):
    def __init__(self, path=None, jdict=None):
        self.channels = dict()
        self.games = dict()
        if path is not None: self.load_path(path)
        if jdict is not None: self.load_jdict(jdict)

    def load_path(self, path):
        jdict = {}
        if os.path.exists(path):
            try:
                with open(path) as file:
                    jdict = json.load(file)
            except:
                traceback.print_exc()
        jdict = recursive_encode(jdict, 'utf-8')
        self.load_jdict(jdict)

    def save_path(self, path):
        with open(path, 'w') as file:
            json.dump(self.save_jdict(), file, indent=4)

    def load_jdict(self, jdict):
        all_urls = set()
        for chan, cdict in jdict.get('channels', dict()).iteritems():
            cobj = Channel(cdict)
            if not cobj.games: continue
            self.channels[chan.lower()] = cobj
            all_urls.update(cobj.games)
        for url, report in jdict.get('games', dict()).iteritems():
            if url not in all_urls: continue
            if report.get('type') == 'report':
                self.games[url] = Report(jdict=report)
            elif report.get('type') == 'error':
                self.games[url] = ErrorReport(url=url, jdict=report)
        for chan, topic in jdict.get('set_topic', dict()).iteritems():
            # Backward compatibility for an obsolete format.
            chan = chan.lower()
            if chan not in self.channels: continue
            self.channels[chan].set_topic = topic

    def save_jdict(self):
        return {
            'games': {
                u: r.save_jdict() for (u,r) in self.games.iteritems()},
            'channels': {
                k: c.save_jdict() for (k,c) in self.channels.iteritems()}}

class Channel(object):
    def __init__(self, jdict=None):
        self.games = []
        self.set_topic = ''
        if jdict is not None:
            self.load_jdict(jdict)
    def load_jdict(self, jdict):
        if isinstance(jdict, list):
            # Backward compatibility for an obsolete format.
            self.games = jdict
        else:
            self.games = jdict.get('games', [])
            self.set_topic = jdict.get('set_topic', '')
    def save_jdict(self):
        return dict(self.__dict__)

class Core(object):
    def __eq__(self, other):
        return type(self) is type(other) \
           and self.core() == other.core()
    def __ne__(self, other):
        return type(self) is not type(other) \
            or self.core() != other.core()
    def __hash__(self, other):
        return hash(self.core())

class Report(Core):
    def __init__(self, jdict=None, url=None, soup=None):
        self.time = time.time()
        self.name = None
        self.turn = None
        self.players = set()
        if jdict is not None: self.load_jdict(jdict)
        if url is not None: self.load_url(url)
        if soup is not None: self.load_soup(soup)

    def load_jdict(self, jdict):
        self.time = jdict.get('time', self.time)
        self.name = jdict.get('name', self.name)
        self.turn = jdict.get('turn', self.turn)
        self.players.update(Player(jdict=d) for d in jdict.get('players', []))

    def save_jdict(self):
        jdict = dict(self.__dict__)
        jdict['players'] = [p.save_jdict() for p in self.players]
        jdict['type'] = 'report'
        return jdict

    def load_url(self, url):
        try:
            stream = util.ext_urlopen(url)
            encoding = stream.info().getparam('charset')
            soup = BeautifulSoup(stream, BS4_PARSER, from_encoding=encoding)
            self.load_soup(soup)
        except urllib2.URLError as e:
            e.exc_info = sys.exc_info()
            raise UnreadableURL('Unable to load <%s>.' % url, exc=e)
        except ValueError as e:
            e.exc_info = sys.exc_info()
            raise UnreadableURL('Unable to load <%s>.' % url, exc=e)
        except UnreadableSoup as e:
            e.exc_info = sys.exc_info()
            raise UnreadableURL('Unable to read status page at <%s>.' % url, exc=e)

    def load_soup(self, soup):
        rows = soup.find_all(name='tr')
        if len(rows) < 1: raise UnreadableSoup(
            'No <tr> elements found in document:\n%s' % soup)
        title = rows[0].text.strip()
        match = re.match(r'(?P<name>.*), turn (?P<turn>\d+)', title)
        if match is None: raise UnreadableSoup(
            'Cannot parse title: %r' % title)
        self.name = recursive_encode(match.group('name'), 'utf8')
        self.turn = int(match.group('turn'))
        for index in range(1, len(rows)):
            self.players.add(Player(index=index, soup=rows[index]))

    def show_text(self, formatter):
        show_players = [
            p for p in self.players if not (
            AI.match(p.status) or ELIMINATED.match(p.status))]
        show_players = sorted(show_players, key=lambda p: p.index)
        return '%s, turn %s [%s]' % (
            formatter.bold(self.name),
            formatter.bold(self.turn),
            ', '.join(p.show_text(formatter)
        for p in show_players))

    def show_diff_text(self, prev, formatter):
        return '%s %s turn %s.' % (
            formatter.bold(self.name),
            'has advanced to' if prev is not None
                and prev.turn is not None and self.turn > prev.turn else
            'has started, at',
            formatter.bold(self.turn))

    def show_topic(self, format=False):
        return self.show_text(formatter=IRCFormatter if format else PlainFormatter)

    def core(self):
        return (self.name, self.turn)

class ErrorReport(Core):
    def __init__(self, url=None, prev=None, exc=None, tstamp=None, jdict=None):
        self.time = tstamp if tstamp is not None else time.time()
        self.url = url
        self.name = prev.name if prev is not None else None
        self.turn = None
        if jdict is not None: self.load_jdict(jdict)
    def load_jdict(self, jdict):
        self.time = jdict.get('time', self.time)
        self.name = jdict.get('name', self.name)
        self.turn = jdict.get('turn', self.turn)
    def save_jdict(self):
        jdict = dict(self.__dict__)
        del jdict['url']
        jdict['type'] = 'error'
        return jdict
    def show_text(self, formatter):
        return ('%s: unable to retrieve status.' % (
            formatter.bold(self.name)
            if self.name is not None else '<%s>' % self.url))
    def show_diff_text(self, prev, formatter):
        return self.show_text(formatter)
    def show_topic(self, format=False):
        return '%s, turn %s [unable to retrieve status]' % (
            self.name if self.name is not None else '?',
            str(self.turn) if self.turn is not None else '?')
    def core(self):
        return ()

class Player(object):
    def __init__(self, index=None, soup=None, jdict=None):
        self.index = index
        self.name = None
        self.css = None
        self.status = None
        if soup is not None: self.load_soup(soup)
        if jdict is not None: self.load_jdict(jdict)
    def load_soup(self, soup):
        cells = soup.select('td')
        if len(cells) < 2: raise UnreadableSoup(
            'Cannot parse body row: %s' % row)
        self.name = recursive_encode(cells[0].text, 'utf8')
        self.status = recursive_encode(cells[1].text, 'utf8')
        self.css = recursive_encode(' '.join(sorted(cells[0].get('class'))), 'utf8')
    def load_jdict(self, jdict):
        self.index = jdict.get('index', self.index)
        self.name = jdict.get('name', self.name)
        self.css = jdict.get('css', self.css)
        self.status = jdict.get('status', self.status)
    def save_jdict(self):
        return self.__dict__
    def show_text(self, formatter):
        return '%s: %s' % (
            self.name.split(',', 1)[0],
            'played' if PLAYED.match(self.status) else
            'unfinished' if UNFINISHED.match(self.status) else
            self.status)
    def id(self):
        return ('Player', self.name, self.status)
    def __cmp__(self, other):
        if type(other) is not Player: return False
        return cmp(self.id(), other.id())
    def __hash__(self):
        return hash(self.id())

class UnreadableURL(Exception):
    def __init__(self, msg, exc=None):
        super(Exception, self).__init__(msg)
        self.exc = exc
    pass

class UnreadableSoup(Exception):
    pass

class TextFormatter(object):
    @staticmethod
    def bold(text):
        raise NotImplementedError('This method must be overridden in a subclass.')

class PlainFormatter(TextFormatter):
    @staticmethod
    def bold(text):
        return text

class IRCFormatter(TextFormatter):
    @staticmethod
    def bold(text):
        return '\2%s\2' % text

state = State(path=STATE_FILE)

#-------------------------------------------------------------------------------
GET_REPORT_MAX_TRIES = 3
GET_REPORT_INTERVAL  = 0.1
@util.mfun(link, 'dominions.get_report')
def get_report(url, ret):
    for tries in xrange(GET_REPORT_MAX_TRIES):
        try:
            yield ret(Report(url=url))
        except UnreadableURL as exc:
            traceback.print_exception(*exc.exc.exc_info)
            if tries < GET_REPORT_MAX_TRIES - 1:
                yield runtime.sleep(GET_REPORT_INTERVAL)
                continue
            else:
                yield ret(ErrorReport(url=url, prev=state.games.get(url), exc=exc))
        return

@util.msub(link, 'dominions.update_urls')
def update_urls(bot, urls, report_to=None, log_level=None):
    msgs = []
    for url in urls:
        prev_report = state.games.get(url)
        report = state.games[url] = yield get_report(url)

        if hasattr(report, 'players') and all(any(r.match(p.status)
        for r in (PLAYED, ELIMINATED, AI)) for p in report.players):
            continue

        if report_to is not None:
            msgs.append((report_to, report.show_text(IRCFormatter)))

        if type(report) is Report \
        and (prev_report is None or report.turn > prev_report.turn) \
        or type(report) is ErrorReport and report != prev_report:
            msgs.extend(
                (chan, report.show_diff_text(prev_report, IRCFormatter))
                for (chan, cobj) in state.channels.iteritems() if url in cobj.games)
            yield sign('dominions.new_turn_report', bot, report, prev_report)

    for chan, cobj in state.channels.iteritems():
        chan_urls = cobj.games
        if set(chan_urls) & set(urls):
            explicit = report_to and chan.lower() == report_to.lower()
            yield update_topic(bot, chan,
                explicit=explicit, log_level=log_level)

    for chan, msg in msgs:
        bot.send_msg(chan, msg)

    if urls:
        state.save_path(STATE_FILE)

@util.mfun(link, 'dominions.update_topic')
def update_topic(bot, chan, ret, explicit=False, **kwds):
    chan = chan.lower()
    new_dyn = '; '.join(
        state.games[url].show_topic()
        for (c, cobj) in state.channels.iteritems() if c == chan
        for url in cobj.games if url in state.games)

    if new_dyn:
        if not explicit and new_dyn in state.channels[chan].set_topic:
            yield ret()
            return

        topic = yield channel.topic(bot, chan)
        topic = '' if topic is None else topic

        if new_dyn in topic:
            yield ret()
            return
    
        match = re.search(
            r'(^|-- )(?P<dyn>(.+, turn (\d+|\?) \[[^\]]*\](; )?)+)( --|$)', topic)
        if match:
            start, end = match.span('dyn')
            topic = ''.join((topic[:start], new_dyn, topic[end:]))
        elif topic:
            topic = ' -- '.join((new_dyn, re.sub(r'^\s*(--)?', '', topic)))
        else:
            topic = new_dyn
        bot.send_cmd('TOPIC %s :%s' % (chan, topic))
        state.channels[chan].set_topic = topic

    yield ret()

@link('DOMINIONS_TICK')
def h_dominions_tick(bot, log_level=None):
    try:
        if not is_installed: return
        urls = []
        latest = time.time() + UPDATE_PERIOD_S
        for chan, cobj in state.channels.iteritems():
            for url in cobj.games:
                if url in urls:
                    continue
                if url in state.games and state.games[url].time > latest:
                    continue
                urls.append(url)
        yield update_urls(bot, urls, log_level=log_level)
    except:
        traceback.print_exc()
    yield runtime.sleep(TICK_PERIOD_S)
    yield sign('DOMINIONS_TICK', bot, log_level=log_level)

@link('!turn')
def h_turn(bot, id, c_chan, args, full_msg):
    chan = c_chan
    if args.startswith('#'):    
        is_admin = yield auth.check(bot, id)
        if is_admin: chan = args
    if not chan: return
    cobj = state.channels.get(chan.lower())
    urls = cobj.games if cobj else []
    yield update_urls(bot, urls, report_to=c_chan)

@link('!dom+')
@auth.admin
@util.further
def h_dom_add(bot, id, c_chan, add_spec, full_msg, cont):
    try:
        aurls = re.findall(r'\S+', add_spec.lower())
        if aurls and aurls[0].startswith('#'): chan = aurls.pop(0)
        else: chan = c_chan

        if chan is None: return
        chan = chan.lower()

        if chan in state.channels:
            cobj = state.channels[chan]
        else:
            cobj = state.channels[chan] = Channel()
        for aurl in aurls:
            if aurl in cobj.games:
                message.reply(bot, id, c_chan,
                    'Error: "%s" is already monitored here.' % aurl)
                break
        else:
            for aurl in aurls:
                cobj.games.append(aurl)

            try:
                state.save_path(STATE_FILE)
            except Exception as e:
                message.reply(bot, id, c_chan, 'Error: %s' % str(e))
                raise
        
            message.reply(bot, id, c_chan, '%d game(s) added.' % len(aurls))
            yield update_urls(bot, aurls, None)
    finally:
        yield cont

@link('!dom-')
@auth.admin
@util.further
def h_dom_del(bot, id, c_chan, del_spec, full_msg, cont):
    try:
        del_spec = re.findall(r'\S+', del_spec.lower())
        if del_spec and del_spec[0].startswith('#'): chan = del_spec.pop(0)
        else: chan = c_chan

        if chan is None: return
        chan = chan.lower()
        if chan not in state.channels: return

        if not del_spec: return
    
        del_urls = []
        for spec in del_spec:
            for i, iurl in izip(count(), state.channels[chan].games):
                if spec == iurl: break
                if spec == str(i+1): break
                if iurl in state.games and spec == state.games[iurl].name: break
            else:
                message.reply(bot, id, c_chan,
                    'Error: no game matching "%s" is monitored here.' % spec)
                return
            del_urls.append(iurl)
        
        del_count = 0
        for durl in del_urls:
            if durl in state.channels[chan].games:
                state.channels[chan].games.remove(durl)
                del_count += 1
            for ochan, ocobj in state.channels.iteritems():
                if durl in ocobj.games: break
            else:
                if durl in state.games: del state.games[durl]

        if not state.channels[chan].games:
            del state.channels[chan]

        try:
            state.save_path(STATE_FILE)
        except Exception as e:
            message.reply(bot, id, c_chan, 'Error: %s' % str(e))
            raise
        message.reply(bot, id, c_chan, '%d game(s) removed.' % del_count)
    finally:
        yield cont

@link('!dom?')
@auth.admin
@util.further
def h_dom_query(bot, id, c_chan, args, full_msg, cont):
    try:
        if args.startswith('#'): chan = args
        else: chan = c_chan

        if not chan: return
        cobj = state.channels.get(chan.lower())
        urls = cobj.games if cobj else []
        if urls:
            for index, url in izip(count(), urls):
                name = getattr(state.games[url], 'name', None) \
                       if url in state.games else None
                message.reply(bot, id, c_chan, '%d. %s%s%s' % (
                    index + 1,
                    url,
                    ' (%s)' % name if name is not None else '',
                    ',' if index < len(urls)-1 else '.'), prefix=False)
        else:
            message.reply(bot, id, c_chan, 'None.', prefix=False)
    finally:
        yield cont
