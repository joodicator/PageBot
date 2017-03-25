from bs4 import BeautifulSoup
import urllib2
import re
import random
import json
import os.path

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
import selenium.webdriver.support.expected_conditions as EC

from untwisted.magic import sign

from url_collect import URL_PART_RE
from url import BS4_PARSER, USER_AGENT
import channel
import runtime
import util
import phantomjs

#===============================================================================
STATE_FILE   = 'state/quora.json'
USED_IDS_MAX = 1000

PAGE_MEAN = 10
PAGE_MAX  = 200

PERIOD_S = 30       # Update every 30 seconds.
MSG_MIN  = (1, 120) # At least 1 message in the last 120*30s (1 hour).
MSG_MAX  = (50, 5)  # At most 50 messages in the last 5*30s (2.5 min).

#===============================================================================
link = util.LinkSet()

def load_conf():
    table = util.table('conf/quora.py')
    return { r.channel.lower(): r for r in table if r.daily_frequency > 0 }

conf = load_conf()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as file:
            return json.load(file)
    return {'used_ids': []}

def save_state(state):
    if state:
        data = json.dumps(state)
        with open(STATE_FILE, 'w') as file:
            file.write(data)

# state = {'used_ids': [id0,id1,...]}
state = load_state()

# msg_count[chan.lower()] = [msgs0, msgs1, ...]
msg_count = {c: [0] * max(MSG_MIN[1], MSG_MAX[1]) for c in conf}

#===============================================================================
def install(bot):
    link.install(bot)
    bot.drive('QUORA_START', bot)

def reload(prev):
    if isinstance(getattr(prev, 'msg_count', None), dict):
        for chan, counts in msg_count.iteritems():
            prev_counts = prev.msg_count.get(chan)
            if not isinstance(prev_counts, list): continue
            if not all(isinstance(n, int) for n in prev_counts): continue
            copy_len = min(len(counts), len(prev_counts))
            msg_count[chan][:copy_len] = prev_counts[:copy_len]

def uninstall(bot):
    link.uninstall(bot)

#===============================================================================
@link('QUORA_START')
def h_quora_start(bot):
    while True:
        yield runtime.sleep(PERIOD_S)
        if not link.installed_modes: return
        for chan, chan_conf in conf.iteritems():
            if random.random() < chan_conf.daily_frequency * PERIOD_S / 86400.0:
                yield sign('QUORA_POST', bot, chan)
        for counts in msg_count.itervalues():
            counts.pop(-1)
            counts.insert(0, 0)

@link('QUORA_POST')
@channel.not_quiet(chan_arg='chan')
def h_quora_post(bot, chan):
    yield runtime.sleep(random.uniform(0, PERIOD_S))
    if not link.installed_modes: return
    if sum(msg_count[chan][:MSG_MIN[1]]) < MSG_MIN[0]: return
    if sum(msg_count[chan][:MSG_MAX[1]]) > MSG_MAX[0]: return

    question = random_question(
        exclude_ids    = state['used_ids'],
        exclude_topics = conf[chan].exclude_topics)
    bot.send_msg(chan, question.text)

    state['used_ids'].append(question.id)
    del state['used_ids'][:-USED_IDS_MAX]
    save_state(state)

@link('MESSAGE', 'COMMAND', 'UNOTICE')
def h_message(bot, id, chan, *args, **kwds):
    if chan is None: return
    counts = msg_count.get(chan.lower())
    if counts is None: return
    counts[0] += 1

#===============================================================================
class Question(object):
    __slots__ = 'id', 'url', '_text', '_topics'
    def __init__(self, url, text=None):
        url_parts = URL_PART_RE.match(url)
        assert url_parts.group('host') == 'www.quora.com'
        assert re.match(r'/[^/?]*$', url_parts.group('path'))
        self.id = url_parts.group('path')[1:].lower()
        self.url = url
        self._text = None if text is None else self.process_text(text)
        self._topics = None

    @property
    def text(self):
        if self._text is None: self.load()
        return self._text

    @property
    def topics(self):
        if self._topics is None: self.load()
        return self._topics

    def load(self):
        with phantomjs.pool.get_driver() as driver:
            driver.get(self.url)
            # Extract the question text, if it is not already known.
            if self._text is None:
                text_element = driver.find_element_by_class_name('question_text_edit')
                self._text = self.process_text(text_element.text.strip())
            # If there is a "view more topics" button, click it and wait until
            # the additional topics are loaded.
            try:
                more = driver.find_element_by_class_name('view_more_topics_link')
            except NoSuchElementException:
                pass
            else:
                more.click()
                prefix = re.sub(r'_more$', r'',
                    more.find_element_by_tag_name('a').get_attribute('id'))
                fetch_into = driver.find_element_by_id(prefix + '_fetch_into')
                WebDriverWait(driver, 5).until(EC.visibility_of(fetch_into))
            # Extract the question topics.
            self._topics = tuple(
                e.text.strip() for e in
                driver.find_elements_by_class_name('QuestionTopicListItem'))

    @staticmethod
    def process_text(text):
        def sub(match):
            if match.group('tag') in ('math', 'code', 'cdata'):
                return match.group('body')
            else:
                return match.group()
        return re.sub(
            r'\[(?P<tag>\w+)[\w\s]*\](?P<body>.*?)\[/(?P=tag)\]', sub, text)

def random_question(exclude_ids=(), exclude_topics=()):
    page = min(1 + int(random.expovariate(1.0/PAGE_MEAN)), PAGE_MAX)
    soup = url_soup('https://www.quora.com/sitemap/recent?page_id=%d' % page)
    qs = soup.find(class_='ContentWrapper') \
             .find('div', recursive=False) \
             .find('div', recursive=False).find_all('a')
    while qs:
        index = random.randrange(len(qs))
        q = qs.pop(index)
        q = Question(url=q['href'], text=q.text.strip())
        if q.id in exclude_ids: continue
        if any(et.lower() == qt.lower()
               for et in exclude_topics for qt in q.topics): continue
        return q

#===============================================================================
def url_soup(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    stream = urllib2.urlopen(request)
    charset = stream.info().getparam('charset')
    return BeautifulSoup(stream, BS4_PARSER, from_encoding=charset)
