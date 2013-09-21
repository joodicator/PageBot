import ctypes

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
    res_ptr = libkakasi.kakasi_do(text.encode(KAKASI_CODEC))
    res = ctypes.string_at(res_ptr).decode(KAKASI_CODEC)
    libkakasi.kakasi_free(res_ptr)
    return res

def is_ja(text, threshold=0.5):
    if type(text) is not unicode: text = text.decode('utf8')
    ja_len = len(filter(lambda c: kakasi_unicode(c) != c, text))
    return float(ja_len)/len(text) > threshold
