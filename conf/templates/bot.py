server   = 'localhost'
port     = 6667
nick     = 'PageBot'
user     = 'PageBot'
name     = 'https://github.com/joodicator/PageBot'

channels = ['#PageBot']

plugins  = [
    'runtime',
    'message',
    'auth',
    'control',
    'channel',

    'chanserv',
    'invite',

    'tell',
    'url_collect',
    'url',
    'aop',
    'seen']
