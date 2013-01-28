from types import MethodType as instancemethod
from types import ClassType as classobj
from collections import namedtuple
from itertools import *
from functools import *
import os.path
import inspect
import random
import sys
import re

ID = namedtuple('ID', ('nick', 'user', 'host'))

# Given a function and an instance, returns an instancemethod appearing as that
# function as a method of the instnace's class, bound to the instance.
def bind(func, inst):
    return instancemethod(func, inst, inst.__class__)

# Reads a list of namedtuples from a file, where each line evalutes to a tuple,
# and the first line is a tuple of strings giving the names. Lines containing
# only whitespace are ignored.
def table(path, name='table_row'):
    with open(path) as file:
        lines = ifilter(re.compile(r'\S').search, file)
        head = namedtuple(name, eval(lines.next()))
        return map(lambda t: head(*t), imap(eval, lines))

# Executes a file of Python statements, returning the resulting dictionary of local
# bindings, in which any top-level classes have been changed to dicts, and, if
# present, in the context of the given dictionary of global bindings.
def fdict(path, globals=None, locals=None):
    if globals == None: globals = dict()
    if locals == None: locals = dict()
    execfile(path, globals, locals)
    return { k: cdict(v) for (k, v) in locals.iteritems()
             if not k.startswith('_') }

# If the given object is a class, returns a copy of its dictionary with any
# __scored__ names removed, otherwise returns the same object unchanged.
def cdict(obj):
    if not isinstance(obj, (type, classobj)): return obj
    return {k:v for (k,v) in obj.__dict__.iteritems()
            if not k.startswith('_')}

# Returns a decorator causing the return value of the decorated function to be
# passed to the given function, whose return value is finally returned.
def after(after):
    return partial(compose, after)

# Replace every handler for the event `find' in the given Mode instance with
# an identical handler for the event `repl'.
def event_sub(mode, find, repl):
    for ((event, func), args) in mode.base.items():
        if event != find: continue
        mode.unlink(find, func)
        mode.link(repl, func)

# Read a list of values from the given file, which must contain one Python
# expression on each non-empty line. The given dictionaries are passed to eval.
def read_list(path, globals=None, locals=None):
    not_empty = re.compile('\S').search
    with open(path) as file:
        return [eval(line, globals, locals) for line in file if not_empty(line)]

# Writes the result of calling repr on each of the given list of values to the
# given file, one one each line.
def write_list(path, list):
    with open(path, mode='w') as file:
        file.writelines(repr(item) + '\r\n' for item in list)

# Returns the functional composition of the two given functions.
def compose(after, before):
    return lambda *a, **k: after(before(*a, **k))

# Returns True if the given module was loaded from a file in or under the
# directory containing the module containing this function, or otherwise False.
def module_is_local(mod):
    if not hasattr(mod, '__file__'): return
    root = os.path.dirname(__file__)
    return os.path.commonprefix([mod.__file__, root]) == root

# Returns the sum of `throws' PRNG-simulated rolls of a `sides'-sided die.
def dice(throws, sides):
    return sum(random.randint(1, sides) for n in xrange(throws))

# Returns the string of length at least `n' resulting from the concatenation of
# the smallest necessary number of spaces to `str'.
def pad_left(str, n):
    return str + ' '*(n - len(str))

# Given a sequence of sequences of strings, representing the rows of a table, each
# row of which contains a number of cells, returns a list of strings representing
# the rows of the table where spaces have been added so that all columns in the
# table are left-aligned and separated by two spaces.
def align_table(lines):
    widths = (imap(len, r) for r in lines)
    widths = [max(t) for t in izip_longest(*widths, fillvalue=0)]
    lines = ((pad_left(*t) for t in izip(l, widths)) for l in lines)
    return ['  '.join(l).strip() for l in lines]


# Returns an object which may be yielded in an untwisted event handler to obtain
# just the given argument, with no other effects.
def just(arg):
    def act(source, chain):
        try: chain.send(arg)(source, chain)
        except StopIteration: pass
    return act

# Returns an object which may be yielded in an untwisted event handler to raise
# the given event in the given Mode instance. Compare: untwisted.mode.sign.
def msign(target, event, *args, **kwds):
    def act(source, chain):
        target.drive(event, *args, **kwds)
    return act

# Returns an object which may be yielded in an untwisted event handler to
# raise `event' with the given arguments, waiting for a response event of the
# form `(event, *args)' with a single argument, and obtaining this argument.
def mcall(event, *args):
    token = (event,) + args
    def act(source, chain):
        def ret(arg):
            source.unlink(token, ret)
            try: chain.send(arg)(source, chain)
            except StopIteration: pass
        source.link(token, ret)
        source.drive(event, *args)
        raise StopIteration
    return act

# A LinkSet maintains a list of bindings between events and event handlers,
# providing some convenience methods for changing and using this list.
class LinkSet(object):
    __slots__ = 'links'
    
    def __init__(self):
        self.links = []
    
    # When called, a LinkSet produces a decorator that just adds a given handler
    # bound to each of the the given events, to its list.
    # IMPORTANT: this decorator should be applied after any other decorators,
    # (i.e. it should be first in the list) so that the right function is bound.
    def __call__(self, event, *args):
        def link(func):
            self.links.append((event, func) + args)
            return func
        return link
    
    # Installs all the current event bindings into the given Mode instance.
    def install(self, mode):
        for link in self.links: mode.link(*link)
    
    # Uninstalls the current event bindings from the given Mode instance.
    def uninstall(self, mode):
        for link in self.links: mode.unlink(*link)
    
    # Maps the given function over the current bindings, returning a pair of
    # functions that respectively install and uninstall the resulting bindings.
    def map(self, func):
        links = map(func, self.links)
        def mapped_install(mode):
            for link in links: mode.link(*link)
        def mapped_uninstall(mode):
            for link in links: mode.unlink(*link)
        return mapped_install, mapped_uninstall
    
    # Syntactic sugar for one-line inclusion in modules.
    def triple(self):
        return self, self.install, self.uninstall

'''
# Given a function which might be called in the following way:
#   def func(finish, *args, **kwds):
#       ...
#       yield sign(token, RETURN_VALUE)
def aync(callee):
    from untwisted.usual import chain, apply
    def decorated(*args, **kwds):
        def act(mode, caller_gen):
            token = object()
            callee_gen = calee(token, *args, **kwds)            
            mode.link(token, result, caller_gen, callee_gen)
            chain(callee_gen)
        return act
    def result(mode, return_value, caller_gen, callee_gen):
        callee_gen.
        try:
            caller_gen.send(return_value)()
            chain(caller_gen)
        except StopIteration: pass            
    return decorated
'''
