from types import MethodType as instancemethod
from types import ClassType as classobj
from collections import namedtuple
from functools import *
from itertools import *
import os.path
import inspect
import random
import sys
import re

ID = namedtuple('ID', ('nick', 'user', 'host'))
ID.__getstate__ = lambda *a, **k: None

from amelia import NotInstalled, AlreadyInstalled

# Reply (in the same channel or by PM, as appropriate) to a message by `id'
# sent to `target' with the message `msg', possibly prefixing the message with
# their nick, unless `prefix' is given as False. For `wrap', see util.send_msg.
def message_reply(bot, id, target, msg, prefix=True, wrap=False, **kwds):
    if prefix and target != None:
        msg = '%s: %s' % (id.nick, msg)
    send_msg(bot, target or id.nick, msg, wrap=wrap, **kwds)

# As bot.send_msg(target, msg), but sends multiple separate messages if wrap
# is True and the message is too long to fit in a single IRC message.
def send_msg(bot, target, msg, wrap=False, **kwds):
    WRAP_LEN, ELLIP = 400, '...'
    while wrap and len(msg) > WRAP_LEN:
        bot.send_msg(target, msg[:WRAP_LEN-len(ELLIP)] + ELLIP, **kwds)
        msg = ELLIP + msg[WRAP_LEN-len(ELLIP):]
    bot.send_msg(target, msg, **kwds)

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
# dictionaries are passed to eval(). If default=True is given, an empty list is
# returned when the file does not exist; otherwise an IOError is raised.
def table(path, name='table_row', globals=None, locals=None, default=False):
    if default and not os.path.exists(path): return []
    lines = read_list(path, globals, locals)
    head = namedtuple(name, lines[0])
    return map(lambda t: head(*t), lines[1:])

# Read a list of values from the given file, which must contain one Python
# expression on each non-empty line not starting with '#'. The given
# dictionaries are passed to eval(). If default=True is given, an empty list is
# returned when the file does not exist; otherwise an IOError is raised.
def read_list(path, globals=None, locals=None, default=False):
    if default and not os.path.exists(path): return []
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
def pad_left(str, n, lenf=len):
    return str + ' '*(n - lenf(str))

# As pad_left, but prepends spaces instead of appending.
def pad_right(str, n, lenf=len):
    return ' '*(n - lenf(str)) + str

# Given some sequences of strings, representing the rows of a table, each
# row of which contains a number of cells, returns a list of strings representing
# the rows of the table where spaces have been added so that all columns in the
# table are left-aligned and separated by two spaces, or the given separator.
def join_rows(*rows, **kwds):
    sep, lenf = kwds.get('sep','  '), kwds.get('lenf', len)
    pad = pad_left if kwds.get('align','l') == 'l' else pad_right
    widths = (imap(lenf, r) for r in rows)
    widths = [max(t) for t in izip_longest(*widths, fillvalue=0)]
    rows = ((pad(*t,lenf=lenf) for t in izip(l, widths)) for l in rows)
    return [sep.join(l).rstrip() for l in rows]

# Alias for join_rows included for back-compatibility.
def align_table(lines, **kwds):
    return join_rows(*lines, **kwds)

# As join_rows, but takes a sequence of columns rather than of rows.
def join_cols(*cols, **kwds):
    return join_rows(*izip_longest(*cols, fillvalue=''), **kwds)

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
# this argument. If 'mcall_token' is given as a keyword argument, this is
# removed and used instead of (event, args, kwds).
def mmcall(mode, event, *args, **kwds):
    import untwisted.usual
    token = kwds.pop('mcall_token', (event,) + args)
    def act(source, chain):
        def ret(arg):
            mode.unlink(token, ret)
            try:
                chain.send(arg)(source, chain)
                untwisted.usual.chain(source, chain)
            except StopIteration: pass
        mode.link(token, ret)
        mode.drive(event, *args, **kwds)
        raise StopIteration
    return act

# As mmcall, but assumes `mode' is the current mode.
def mcall(event, *args, **kwds):
    import untwisted.usual
    token = kwds.pop('mcall_token', (event,) + args)
    def act(source, chain):
        def ret(arg, **kwds):
            source.unlink(token, ret)
            try:
                chain.send(arg)(source, chain)
                untwisted.usual.chain(source, chain)
            except StopIteration: pass
        source.link(token, ret)
        source.drive(event, *args, **kwds)
        raise StopIteration
    return act

#===============================================================================
#   @mfun(link, event_name)
#   def func(*args, **kwds):
#       ...
#       yield kwds['ret'](return_value)
#       ...
#
# -is equivalent to-
#
#   def func(*args):
#       return mcall(event_name, *args)
#
#   @link(event_name)
#   def h_func(*args):
#       ...
#       yield sign((event_name,)+args, return_value)
#       ...
def mfun(link, event_name):
    def mfun_dec(fun):
        @link(event_name)
        def mfun_han(token, *args, **kwds):
            from untwisted.magic import sign
            ret = lambda r=None: sign(token, r, log_level=kwds.get('log_level'))
            return fun(*args, ret=ret, **kwds)
        def mfun_fun(*args, **kwds):
            token = ('util.mfun', event_name, object())
            return mcall(event_name, token, *args, mcall_token=token, **kwds)
        return mfun_fun
    return mfun_dec

#===============================================================================
# As mfun, but for non-blocking functions that do not return an argument.
def msub(link, event_name):
    def msub_dec(fun):
        link(event_name)(fun)
        return lambda *args, **kwds: sub(fun(*args, **kwds))
    return msub_dec

#===============================================================================
# When yielded from an untwisted event handler, runs the handler invocation from
# which sub_gen is the return value.
def sub(sub_gen):
    import untwisted.usual
    def action(mode, super_gen):
        if not inspect.isgenerator(sub_gen): return
        gen = gen_chain(sub_gen, super_gen)
        untwisted.usual.chain(mode, gen)
        raise StopIteration
    return action

# As mmcall, but takes several tuples (event, *args) giving multiple calls
# to perform concurrently, their results returned in a list.
def mmcall_all(mode, *calls):
    from untwisted.magic import hold
    token = ('mmcall_all', object())

    def mmcall_wait():
        mode.unlink(token, mmcall_wait)
        wait_calls = list(calls)
        results = [None for c in wait_calls]
        complete = [False for c in wait_calls]
        while not all(complete):
            wait_call, (result,) = yield hold(mode, *filter(id, wait_calls))
            i = wait_calls.index(wait_call)
            results[wait_calls.index(wait_call)] = result
            complete[i] = True
            wait_calls[i] = None
        yield msign(mode, (token,), results)
    mode.link(token, mmcall_wait)

    def mmcall_send():
        mode.unlink(token, mmcall_send)
        for call in calls:
            yield msign(mode, *call)
    mode.link(token, mmcall_send)

    return mmcall(mode, token)

# A LinkSet maintains a list of bindings between events and event handlers,
# providing some convenience methods for changing and using this list.
class LinkSet(object):
    __slots__ = 'links', 'modules', 'installed_modes'
    
    def __init__(self):
        self.links = []
        self.installed_modes = set()
    
    # When called, a LinkSet produces a decorator that just adds a given handler
    # bound to each of the the given events, to its list.
    # IMPORTANT: this decorator should be applied after any other decorators,
    # (i.e. it should be first in the list) so that the right function is bound.
    def __call__(self, *events, **kwds):
        def link(func):
            unique_func = lambda *a, **k: func(*a, **k)
            for event in events:
                self.link(event, unique_func, **kwds)
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
        if mode in self.installed_modes: raise AlreadyInstalled
        for link in self.links:
            if link[0] == 'link':
                (_, args, kwds) = link
                mode.link(*args, **kwds)
            elif link[0] == 'link_module':
                (_, mod, args, kwds) = link
                mod.install(mode, *args, **kwds)
        self.installed_modes.add(mode)
    
    # Uninstalls the current event bindings from the given Mode instance.
    def uninstall(self, mode):
        if mode not in self.installed_modes: raise NotInstalled
        for link in self.links:
            if link[0] == 'link':
                (_, args, kwds) = link
                mode.unlink(*args, **kwds)
            elif link[0] == 'link_module':
                (_, mod, args, kwds) = link
                mod.uninstall(mode)
        self.installed_modes.remove(mode)
    
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
    cre = '|'.join(re.escape(cmd) for cmd in sorted(cmds, key=len, reverse=True))
    cre = re.compile('(?:%s)(?:\s|$)'%cre, re.I)
    def multi_deco(func):
        def multi_func(bot, id, target, args, *extra):
            argss = re.split(cre, args)
            def plain_reply(msg):
                message_reply(bot, id, target, msg, prefix=prefix)
            for (index, sub_args) in izip(count(1), argss):
                if limit and index > limit:
                    plain_reply('(further invocations ignored).')
                    break
                def multi_reply(msg):
                   plain_reply('[%d] %s' % (index, msg))
                yield sub(func(bot, id, target, sub_args.strip(), *extra,
                    reply=multi_reply if len(argss)>1 else plain_reply))
        return multi_func
    return multi_deco

#===============================================================================
# Decorates a !command event handler so that, within its arguments, any
# occurrence of '!' followed by one or more non-space characters will cause this
# to be removed from the arguments and issued as a separate command. The handler
# must accept an additional argument, 'cont', to be yielded after it is complete.
def further(func):
    from untwisted.magic import sign
    def further_fun(bot, id, target, args, full_msg):
        match = re.search(r'(?P<cmd>!\S+)\s*(?P<args>.*)', args)
        if match:
            scmd = match.group('cmd')
            sargs = match.group('args')
            args = args[:match.start()]
            cont = sign('COMMAND', bot, id, target, scmd, sargs, full_msg)
            return func(bot, id, target, args, full_msg, cont)
        else:
            return func(bot, id, target, args, full_msg, lambda *args: None)
    return further_fun

#===============================================================================
# As itertools.chain, but supports the send() method, and requires all arguments
# to be generators (or otherwise to support send()).
def gen_chain(*gens):
    for gen in gens:
        value = None
        try:
            while True:
                value = yield gen.send(value)
        except StopIteration:
            pass

#==============================================================================#
# Returns a Python regular expression pattern string equivalent to the given
# wildcard pattern (which accepts only the entire input, not part of it).
def wc_to_re(wc):
    def sub(match):
        if match.group(1): return '.*'
        elif match.group(2): return '.'
        else: return re.escape(match.group(3))
    return '^' + re.sub(r'(\*)|(\?)|([^*?]+)', sub, wc) + '$'


#===============================================================================
# Given a module install and uninstall function, returns a new pair of such
# functions which enforce the given module names as dependencies, to be
# installed first.
def depend(install, uninstall, *deps):
    installed = [False]

    def depend_install(mode):
        if installed[0]: raise AlreadyInstalled
        for dep in deps:
            try: __import__(dep).install(mode)
            except AlreadyInstalled: pass
        try: install(mode)
        except AlreadyInstalled: pass
        installed[0] = True

    def depend_uninstall(mode):
        if not installed[0]: raise NotInstalled
        try: uninstall(mode)
        except NotInstalled: pass
        installed[0] = False

    return depend_install, depend_uninstall

#===============================================================================
# Given a structure of dicts, lists and tuples, returns an equivalent structur
# with encode() mapped over all unicode values contained therein.
def recursive_encode(object, codec, done=None):
    if done is None:
        done = dict()
    if id(object) in done:
        return done[id(object)]

    result = None
    if type(object) is unicode:
        result = object.encode(codec)
    elif type(object) is dict:
        result = { recursive_encode(k, codec, done)
                   : recursive_encode(v, codec, done)
                   for (k,v) in object.iteritems() }
    elif type(object) is list:
        result = [ recursive_encode(v, codec, done)
                   for v in object ]
    elif type(object) is tuple:
        result = tuple( recursive_encode(v, codec, done)
                        for v in object )
    else:
        result = object

    done[id(object)] = result
    return result

# The longest (contiguous) substring common to seq1 and seq2.
# Computed in O(len(seq1)*len(seq2)) time and space.
def longest_common_substr(seq1, seq2):
    len1, len2 = len(seq1), len(seq2)
    if len1 > len2:
        seq1, seq2, len1, len2 = seq2, seq1, len2, len1
    bend, blen = 0, 0
    for d in xrange(len2-1):
        cend, clen = 0, 0
        for i in xrange(min(len1, len2-d)):
            if seq1[i] == seq2[i+d]:
                cend, clen = i+1, clen+1
                if clen > blen:
                    bend, blen = cend, clen
            else:
                clen = 0
    return seq1[bend-blen:bend]

# The longest common subsequence of s and t, as a list.
def longest_common_subseq(s, t):
    l = longest_common_subseq_len_matrix(s, t)
    i, j, r = len(s), len(t), []
    while l[i][j]:
        if l[i][j] == l[i-1][j-1]:
            i -= 1
        elif l[i][j] == l[i][j-1]:
            j -= 1
        else:
            i -= 1
            j -= 1
            r.insert(0, s[i])
    return r

# len(longest_common_subseq(s, t))
def longest_common_subseq_len(s, t):
    return longest_common_subseq_len_matrix(s, t)[-1][-1]

# A list of lists l with the property:
#   l[i][j] == longest_common_subseq_len(s[:i], t[:j])
#   for all i in range(len(s)+1), j in range(len(t)+1)
# computed using O(len(s)*len(t)) time and space.
def longest_common_subseq_len_matrix(s, t):
    m, n = len(s), len(t)
    l = [[0 for j in xrange(n+1)] for i in xrange(m+1)]
    for i in xrange(1, m+1):
        for j in xrange(1, n+1):
            if s[i-1] == t[j-1]:
                l[i][j] = l[i-1][j-1] + 1
            else:
                l1 = l[i-1][j]
                l2 = l[i][j-1]
                l[i][j] = l1 if l1 > l2 else l2
    return l

lcsstr = longest_common_substr
lcsseq = longest_common_subseq
lcsseql = longest_common_subseq_len
lcsseqm = longest_common_subseq_len_matrix
