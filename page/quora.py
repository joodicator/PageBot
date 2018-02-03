from itertools import *
import urllib2
import re
import random
import json
import os.path
import traceback

from bs4 import BeautifulSoup

from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
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

ALL_PAGE_MEAN = 10
ALL_PAGE_MAX  = 200
TOPIC_Q_MEAN  = 50
TOPIC_Q_MAX   = 500

PERIOD_S = 30        # Update every 30 seconds.
MSG_MIN  = (1, 1440) # At least 1 message in the last 1440*30s (12 hours).
MSG_MAX  = (30, 5)   # At most 30 messages in the last 5*30s (2.5 min).

#===============================================================================
class MetaTopic(object):
    __slots__ = 'name', '_topics'
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return 'MetaTopic(%r)' % self.name
    @property
    def topics(self):
        if not hasattr(self, '_topics'):
            self._topics = meta_topics(self.name)
        return self._topics

#===============================================================================
link = util.LinkSet()

def load_conf():
    table = util.table('conf/quora.py', globals={'meta': MetaTopic})
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
                try:
                    yield sign('PRE_QUORA_POST', bot, chan)
                except:
                    traceback.print_exc()
        for counts in msg_count.itervalues():
            counts.pop(-1)
            counts.insert(0, 0)

@link('PRE_QUORA_POST')
@channel.not_quiet(chan_arg='chan')
def h_quora_post(bot, chan):
    yield runtime.sleep(random.uniform(0, PERIOD_S))
    if not link.installed_modes: return
    if sum(msg_count[chan][:MSG_MIN[1]]) < MSG_MIN[0]: return
    if sum(msg_count[chan][:MSG_MAX[1]]) > MSG_MAX[0]: return

    exclude_topics = getattr(conf[chan], 'exclude_topics', ())
    if type(exclude_topics) is not tuple: exclude_topics = (exclude_topics,)
    source_topics = getattr(conf[chan], 'source_topics', ())
    if type(source_topics) is not tuple: source_topics = (source_topics,)
    question = random_question(
        exclude_ids    = state['used_ids'],
        exclude_topics = exclude_topics,
        source_topics  = source_topics)
    bot.send_msg(chan, question.text)

    state['used_ids'].append(question.id)
    del state['used_ids'][:-USED_IDS_MAX]
    save_state(state)

    yield sign('QUORA_POST', bot, chan, question)

@link('MESSAGE', 'COMMAND', 'UNOTICE')
def h_message(bot, id, chan, *args, **kwds):
    if chan is None: return
    counts = msg_count.get(chan.lower())
    if counts is None: return
    counts[0] += 1

#===============================================================================
class Question(object):
    __slots__ = 'id', 'url', '_text', '_topics'
    def __init__(self, id=None, url=None, text=None):
        if id is None and url is not None:
            url_parts = URL_PART_RE.match(url)
            assert url_parts.group('host') == 'www.quora.com', url
            assert re.match(r'/[^/?]*$', url_parts.group('path')), url
            self.id = url_parts.group('path')[1:].lower()
            self.url = url
        elif url is None and id is not None:
            self.id = id.lower()
            self.url = 'https://www.quora.com/%s' % id
        else:
            raise ValueError('The arguments "id" and "url" are both None.')
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
                text_el = driver.find_element_by_class_name('question_text_edit')
                self._text = self.process_text(text_el.text.strip())
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
                WebDriverWait(driver, 6).until(EC.visibility_of(fetch_into))
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

def random_question(exclude_ids=(), exclude_topics=(), source_topics=()):
    if not source_topics:
        return random_question_all(exclude_ids, exclude_topics)

    topics = []
    for topic in source_topics:
        if isinstance(topic, MetaTopic):
            topics.extend(topic.topics)
        elif isinstance(topic, str):
            topics.append(topic)

    exclude_topics = map(str.lower, exclude_topics)
    for q, n in izip(topic_questions(random.choice(topics)), count()):
        if n < TOPIC_Q_MAX and random.random() > 1.0/TOPIC_Q_MEAN: continue
        if q.id in exclude_ids: continue
        if any(t.lower() in exclude_topics for t in q.topics): continue
        return q

def random_question_all(exclude_ids=(), exclude_topics=()):
    exclude_topics = map(str.lower, exclude_topics)
    page = min(1 + int(random.expovariate(1.0/ALL_PAGE_MEAN)), ALL_PAGE_MAX)
    soup = url_soup('https://www.quora.com/sitemap/recent?page_id=%d' % page)
    qs = soup.find(class_='ContentWrapper') \
             .find('div', recursive=False) \
             .find('div', recursive=False).find_all('a')
    while qs:
        index = random.randrange(len(qs))
        q = qs.pop(index)
        q = Question(url=q['href'], text=q.text.strip())
        if q.id in exclude_ids: continue
        if any(t.lower() in exclude_topics for t in q.topics): continue
        return q

# Returns an interator of Question instances taken from the "all questions" feed
# of the given topic.
TOPIC_QUESTIONS_URL = 'https://www.quora.com/topic/%s/all_questions' 
def topic_questions(topic):
    with phantomjs.pool.get_driver() as driver:
        driver.get(TOPIC_QUESTIONS_URL % re.sub(r'\W+', '-', topic))

        # If this topic has been "merged into" another topic, redirect to it.
        divs = driver.find_elements_by_class_name('TopicUnmergeSentence')
        if divs:
            a = divs[0].find_element_by_class_name('TopicNameLink')
            topic = re.search(r'/topic/([^/]+)/', a.get_attribute('href')).group(1)
            driver.get(TOPIC_QUESTIONS_URL % topic)

        seen_ids = set()
        while True:
            # Yield all currently loaded questions that have not yet been seen.
            qlist = driver.find_element_by_class_name('TopicAllQuestionsList')
            qs = qlist.find_elements_by_class_name('pagedlist_item')
            any_new = False
            for q in qs:
                if q.get_attribute('id') in seen_ids: continue
                seen_ids.add(q.get_attribute('id'))
                a = q.find_element_by_class_name('question_link')
                q_id = re.sub(r'^.*/', '', a.get_attribute('href'))
                q_text = a.get_property('innerText').strip()
                yield Question(id=q_id, text=q_text)
                any_new = True

            # If there are no new questions, we have reached the end of the list
            # or there is some error; in any case, stop yielding questions.
            if not any_new: break

            # Click the "More" button to load more questions and wait for the
            # loading indicator to appear and then (after up to 10s) disappear.
            m_div = qlist.find_element_by_class_name('PagedListMoreButton')
            m_id = m_div.get_attribute('id')
            m_id = re.sub(r'_paged_list_more_button$', '', m_id)
            m_load = m_div.find_element_by_id(m_id + '_loading')

            driver.execute_script(
                'document.getElementById("%s_more").click();' % m_id)
            try:
                WebDriverWait(driver, timeout=0.5, poll_frequency=0.005).until(
                    lambda d: m_load.value_of_css_property('display') != 'none')
            except TimeoutException:
                pass
            else:
                WebDriverWait(driver, timeout=20, poll_frequency=0.1).until(
                    lambda d: m_load.value_of_css_property('display') == 'none')

# Returns a tuple of topics in the given category, as listed in Quora's sitemap.
def meta_topics(category):
    return tuple(meta_topics_iter(category))

def meta_topics_iter(category):
    soup = url_soup('https://www.quora.com/sitemap')
    dt = soup.find('dt', string=category)
    if dt is None: raise ValueError('Topic category "%s" not found.' % category)
    for dd in dt.find_parent('dl').find_all('dd'):
        link = dd.find(class_='TopicNameLink')
        yield re.search(r'/topic/([^/]+)', link['href']).group(1).strip()

#===============================================================================
def url_soup(url):
    request = urllib2.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    stream = urllib2.urlopen(request)
    charset = stream.info().getparam('charset')
    return BeautifulSoup(stream, BS4_PARSER, from_encoding=charset)
