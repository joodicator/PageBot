from untwisted.network import sign
from untwisted.event import *


def shrug(obj, stack, delim='\r\n'):
    chain = stack.split(delim)
    for chunk in chain[:-1]:
        yield sign(FOUND, obj, chunk)
    obj.stack = chain[-1]

def yuck(obj, stack, size=1024):
    pass

def charset(obj, name='utf-8'):
    obj.data = obj.data.decode(name, 'replace')

def append(obj):
    """ 
        This function appends obj.data to obj.stack.
        Sometimes it isn't needed as when transfering files.
    """
    obj.stack = obj.stack + obj.data
    yield sign(BUFFER, obj, obj.stack)
