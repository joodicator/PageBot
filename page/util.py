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
ID.__getstate__ = lambda *a, **k: None

# Reply (in the same channel or by PM, as appropriate) to a message by `id'
# sent to `target' with the message `msg', possibly prefixing the message with
# their nick, unless `prefix' is given as False.
def message_reply(bot, id, target, msg, prefix=True):
    if prefix and target != None:
        msg = '%s: %s' % (id.nick, msg)
    bot.send_msg(target or id.nick, msg)

# Given a function and an instance, returns an instancemethod appearing as that
# function as a method of the instnace's class, bound to the instance.
def bind(func, inst):
    return instancemethod(func, inst, inst.__class__)

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

# Reads a list of namedtuples from a file, where each line evalutes to a tuple,
# and the first line is a tuple of strings giving the names. Lines containing
# only whitespace or starting with '#' are ignored. The given global and local
# dictionaries are passed to eval().
def table(path, name='table_row', globals=None, locals=None):
    lines = read_list(path, globals, locals)
    head = namedtuple(name, lines[0])
    return map(lambda t: head(*t), lines[1:])

# Read a list of values from the given file, which must contain one Python
# expression on each non-empty line not starting with '#'.
# The given dictionaries are passed to eval().
def read_list(path, globals=None, locals=None):
    not_empty = re.compile('\S').search
    with open(path) as file:
        return [eval(line, globals, locals) for line in file
                if not_empty(line) and not line.startswith('#')]

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
    if hasattr(mod, '__is_local__'): return mod.__is_local__
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

# As pad_left, but prepends spaces instead of appending.
def pad_right(str, n):
    return ' '*(n - len(str)) + str

# Given a sequence of sequences of strings, representing the rows of a table, each
# row of which contains a number of cells, returns a list of strings representing
# the rows of the table where spaces have been added so that all columns in the
# table are left-aligned and separated by two spaces, or the given separator.
def align_table(lines, sep='  ', align='l'):
    pad = {'l': pad_left, 'r': pad_right}[align]
    widths = (imap(len, r) for r in lines)
    widths = [max(t) for t in izip_longest(*widths, fillvalue=0)]
    lines = ((pad(*t) for t in izip(l, widths)) for l in lines)
    return [sep.join(l).rstrip() for l in lines]


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
# raise `event' in `mode' with the given arguments, waiting for a response
# event of the form `(event, *args)' with a single argument, and obtaining
# this argument.
def mmcall(mode, event, *args):
    import untwisted.usual
    token = (event,) + args
    def act(source, chain):
        def ret(arg):
            mode.unlink(token, ret)
            try:
                chain.send(arg)(source, chain)
                untwisted.usual.chain(source, chain)
            except StopIteration: pass
        mode.link(token, ret)
        mode.drive(event, *args)
        raise StopIteration
    return act

# As mmcall, but assumes `mode' is the current mode.
def mcall(event, *args):
    import untwisted.usual
    token = (event,) + args
    def act(source, chain):
        def ret(arg):
            source.unlink(token, ret)
            try:
                chain.send(arg)(source, chain)
                untwisted.usual.chain(source, chain)
            except StopIteration: pass
        source.link(token, ret)
        source.drive(event, *args)
        raise StopIteration
    return act

# A LinkSet maintains a list of bindings between events and event handlers,
# providing some convenience methods for changing and using this list.
class LinkSet(object):
    __slots__ = 'links', 'modules'
    
    def __init__(self):
        self.links = []
    
    # When called, a LinkSet produces a decorator that just adds a given handler
    # bound to each of the the given events, to its list.
    # IMPORTANT: this decorator should be applied after any other decorators,
    # (i.e. it should be first in the list) so that the right function is bound.
    def __call__(self, *events, **kwds):
        def link(func):
            for event in events:
                self.link(event, func, **kwds)
            return func
        return link

    def link(self, *args, **kwds):
        self.links.append(('link', args, kwds))
    
    def unlink(self, *args, **kwds):
        self.links.remove(('link', args, kwds))

    def link_module(self, mod, *args, **kwds):
        self.links.append(('link_module', mod, args, kwds))

    def unlink_module(self, mod, *args, **kwds):
        self.links.remove(('link_module', mod, args, kwds))

    # Installs all the current event bindings into the given Mode instance.
    def install(self, mode):
        for link in self.links:
            if link[0] == 'link':
                (_, args, kwds) = link
                mode.link(*args, **kwds)
            elif link[0] == 'link_module':
                (_, mod, args, kwds) = link
                mod.install(mode, *args, **kwds)
    
    # Uninstalls the current event bindings from the given Mode instance.
    def uninstall(self, mode):
        for link in self.links:
            if link[0] == 'link':
                (_, args, kwds) = link
                mode.unlink(*args, **kwds)
            elif link[0] == 'link_module':
                (_, mod, args, kwds) = link
                mod.uninstall(mode)
    
    # Syntactic sugar for one-line inclusion in modules.
    def triple(self):
        return self, self.install, self.uninstall

#===============================================================================
# Decorates a !command event handler, so that it accepts multiple invocations on
# a single line, whose arguments are separated by the given strings, which will
# typically be the events ('!cmd1', '!cmd2', ...) that the event handler is
# bound to.
#
# The event handler must accept an additional keyword argument called called
# 'reply', which is a function reply(msg) with similar semantics to
# message.reply; but which prepends '[%d] '%index to msg, where index is the
# 1-based index of the sub-invocation of the command (unless only 1 invocation
# is given, in which case nothing is prepended); and taking its 'prefix'
# argument from the arguments to multi(). This should usually be used instead
# of replying directly to the command.
#
# If limit=N is given, only the first N invocations are processed, with an
# explanatory message supplied to the invoker when more than N are supplied,
# in the same style as the reply() function would otherwise have been given.
def multi(*cmds, **kwds): # limit=None, prefix=True
    limit = kwds.get('limit', None)
    prefix = kwds.get('prefix', True)
    cre = '|'.join(re.escape(cmd) for cmd in cmds)
    cre = re.compile('(?:%s)(?:\s|$)'%cre, re.I)
    def multi_deco(func):
        def multi_func(bot, id, target, args, *extra):
            argss = re.split(cre, args)
            plain_reply = lambda msg: message_reply(bot, id, target, msg)
            for (index, sub_args) in izip(count(1), argss):
                if limit and index > limit:
                    return plain_reply('(further invocations ignored).')
                if len(argss) > 1:
                    reply = lambda msg: plain_reply('[%d] %s' % (index, msg))
                else: reply = plain_reply

                yield sub(func(bot, id, target, sub_args.strip(), *extra, reply))
        return multi_func
    return multi_deco

#===============================================================================
# When yielded from an untwisted event handler, runs the handler invocation from
# which sub_gen is the return value.
def sub(sub_gen):
    import untwisted.usual
    def action(mode, gen):
        if not inspect.isgenerator(sub_gen): return
        chain = itertools.chain(sub_gen, gen)
        untwisted.usual.chain(mode, chain)
        raise StopIteration
    return action
