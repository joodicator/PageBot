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

init_kakasi('-Ea', '-Ka', '-Ha', '-Ja', '-s', '-p', '-rhepburn')

def kakasi(text):
    if type(text) is unicode:
        return kakasi_unicode(text)
    elif type(text) is str:
        return kakasi_unicode(text.decode('utf8')).encode('utf8')
    else:
        raise TypeError('utf8 str or unicode expected.')

def kakasi_unicode(text):
    text = text.encode(backslash_escape(KAKASI_CODEC), 'backslashreplace')
    res_ptr = libkakasi.kakasi_do(text)
    res = ctypes.string_at(res_ptr).decode(KAKASI_CODEC)
    libkakasi.kakasi_free(res_ptr)
    return backslash_unescape(res)

def is_ja(text, threshold=0.5):
    return ja_quotient(text) > threshold

def ja_quotient(text):
    if type(text) is not unicode: text = text.decode('utf8')
    ja_len = len(filter(lambda c: kakasi_unicode(c) != c, text))
    return float(ja_len)/len(text)

def backslash_escape(str):
    return re.sub(r'\\', r'\\\\', str)

def backslash_unescape(str):
    def sub(m):
        s = m.group(1)
        return unichr(int(s[1:], 16)) if s[0]=='u' else s
    return re.sub(r'\\(\\|u[0-9a-f]{4})', sub, str, re.I)
