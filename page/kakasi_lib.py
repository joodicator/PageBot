# coding=utf8

import ctypes
import re

libkakasi = None
KAKASI_CODEC = 'sjis'

def init_kakasi(*args):
    global libkakasi
    args = ('kakasi',) + tuple(args) + ('-i'+KAKASI_CODEC, '-o'+KAKASI_CODEC)
    libkakasi = ctypes.CDLL('libkakasi.so')
    libkakasi.kakasi_do.restype = ctypes.c_void_p
    libkakasi.kakasi_getopt_argv(len(args), (ctypes.c_char_p * len(args))(*args))

init_kakasi('-Ka', '-Ha', '-Ja', '-s', '-p', '-rhepburn')

def kakasi(text):
    if type(text) is unicode:
        return kakasi_unicode(text)
    elif type(text) is str:
        return kakasi_unicode(text.decode('utf8')).encode('utf8')
    else:
        raise TypeError('utf8 str or unicode expected.')

def kakasi_unicode(text):
    if not text: return text
    text = pre_kakasi_unicode(text)
    text = backslash_escape(text).encode(KAKASI_CODEC, 'backslashreplace')
    res_ptr = libkakasi.kakasi_do(text)
    res = ctypes.string_at(res_ptr).decode(KAKASI_CODEC)
    if res: libkakasi.kakasi_free(res_ptr)
    res = backslash_unescape(res)
    res = post_kakasi_unicode(res)
    return res

def pre_kakasi_unicode(text):
    return text.replace(u'ー', u'~')

def post_kakasi_unicode(text):
    return text

def is_ja(text, threshold=0.5):
    return ja_quotient(text) > threshold

def ja_quotient(text):
    if type(text) is not unicode: text = text.decode('utf8')
    def char_is_ja(c):
        k = kakasi_unicode(c)
        return k and k != c
    ja_len = len(filter(char_is_ja, text))
    return float(5*ja_len)/(4*len(text)+ja_len)

def backslash_escape(str):
    return re.sub(r'\\', r'\\\\', str)

def backslash_unescape(str):
    def sub(m):
        s = m.group(1)
        return unichr(int(s[1:], 16)) if s[0] in 'xuU' else s
    return re.sub(
        r'\\(\\|x[0-9a-f]{2}|u[0-9a-f]{4}|U[0-9a-f]{8})', sub, str)
