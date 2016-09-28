# coding=utf8

from ctypes import *
import string
import re

import util

libkakasi = None
KAKASI_CODEC = 'sjis'

def init_kakasi(*args):
    global libkakasi
    args = ('kakasi',) + tuple(args) + ('-i'+KAKASI_CODEC, '-o'+KAKASI_CODEC)
    libkakasi = CDLL('libkakasi.so.2')

    libkakasi.kakasi_getopt_argv.restype = c_int
    libkakasi.kakasi_getopt_argv.argtypes = c_int, POINTER(c_char_p)

    libkakasi.kakasi_do.restype = POINTER(c_char)
    libkakasi.kakasi_do.argtypes = c_char_p,

    libkakasi.kakasi_free.restype = c_int
    libkakasi.kakasi_free.argtypes = c_char_p,

    libkakasi.kakasi_getopt_argv(len(args), (c_char_p * len(args))(*args))

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
    res = string_at(res_ptr).decode(KAKASI_CODEC)
    libkakasi.kakasi_free(res_ptr)
    res = backslash_unescape(res)
    res = post_kakasi_unicode(res)
    return res

def pre_kakasi_unicode(text):
    return text.replace(u'ー', u'~')

def post_kakasi_unicode(text):
    return text

def is_ja(text, threshold=0.3):
    return ja_quotient(text) > threshold

def ja_quotient(text):
    if len(text) == 0: return 0
    if type(text) is not unicode: text = text.decode('utf-8')
    jtext = kakasi_unicode(text)
    splen = len(re.sub(r'[^\s\x00-\x1f]', '', text))
    njlen = util.longest_common_subseq_len(text, jtext)
    return float(len(text) - njlen - splen)/(len(text) - splen)

def backslash_escape(str):
    return re.sub(r'\\', r'\\\\', str)

def backslash_unescape(str):
    def sub(m):
        s = m.group(1)
        return unichr(int(s[1:], 16)) if s[0] in 'xuU' else s
    return re.sub(
        r'\\(\\|x[0-9a-f]{2}|u[0-9a-f]{4}|U[0-9a-f]{8})', sub, str)
