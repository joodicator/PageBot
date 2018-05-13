import time as m_time

from util import LinkSet, ID, NotInstalled, AlreadyInstalled
import identity
import channel

link, install, uninstall = LinkSet().triple()

#===============================================================================
# Support classes:
#===============================================================================

# Any class whose __metaclass__ attribute is explicitly set to AbstractSlots
# becomes an abstract class. The __slots__ attribute of any subclass *without*
# an explicit __metaclass__ attribute is extended with all of the names in the
# __slots__ attribute of each of its abstract superclasses.
class AbstractSlots(type):
    def __new__(mcs, name, bases, dict):
        __ab_slots = '_AbstractSlots__ab_slots'
        slots = []
        for base in bases:
            if not hasattr(base, __ab_slots): continue
            slots.extend(a for a in getattr(base, __ab_slots) if a not in slots)
        cls_slots = dict.get('__slots__')
        if cls_slots is not None:
            if isinstance(cls_slots, str): slots.append(cls_slots)
            else: slots.extend(a for a in dict['__slots__'] if a not in slots)

        if '__metaclass__' in dict:
            dict[__ab_slots] = tuple(slots)
            dict['__slots__'] = ()

            assert '__new__' not in dict
            def __new__(subcls, *args, **kwds):
                if getattr(subcls, __ab_slots): raise TypeError(
                    "Can't instantiate abstract class %s." % name)
                return super(cls, subcls).__new__(subcls, *args, **kwds)
            dict['__new__'] = __new__

        else:
            dict['__slots__'] = tuple(slots)
            dict[__ab_slots] = ()

        cls = super(AbstractSlots, mcs).__new__(mcs, name, bases, dict)
        return cls

# This mixin class provides a __repr__ method based on the instance's __slots__
# and type __name__, similar to that of collections.namedtuple.
class ReprSlots(object):
    __slots__ = ()
    def __repr__(self):
        slots = (a for a in iter_slots(self) if hasattr(self, a))
        attrs = ('%s=%r' % (a, getattr(self, a)) for a in slots)
        return '%s(%s)' % (type(self).__name__, ', '.join(attrs))

# This mixin class provides an __init__ method that assigns each keyword
# argument as an instance attribute, or raises ArgumentError if there is any
# keyword not corresponding to a slot, or any slot remaining without a set value.
class InitSlots(object):
    __slots__ = ()
    def __init__(self, **kwds):
        super(InitSlots, self).__init__()
        for slot in iter_slots(self):
            if slot in kwds:
                setattr(self, slot, kwds.pop(slot))
            elif not hasattr(self, slot):
                raise ArgumentError('Missing keyword argument: %s.' % slot)
        if kwds:
            raise ArgumentError('Unexpected keyword argument%s: %s.'
                  % ('s' if len(kwds) > 1 else '', ', '.join(kwds.iterkeys())))

# Return an iterator over the unique __slots__ names in the given class and
# its superclasses, ordered from superclass to subclass, from left to right.
def iter_slots(inst, seen=None):
    if seen is None: seen = set()
    for base in type(inst).__bases__:
        if base in seen: continue
        seen.add(base)
        for slot in iter_slots(base, seen): yield slot

    slots = getattr(inst, '__slots__', None)
    if slots is None: return
    for slot in (slots,) if isinstance(slots, str) else slots:
        if slot in seen: continue
        yield slot
        seen.add(slot)

#===============================================================================
# Miscellaneous data classes:
#===============================================================================

# IRCActor(name, **k)     -> IRCServer(name=name, **k)
# IRCActor(id, **k)       -> IRCUser(id=id, **k)
# IRCActor(id, chan, **k) -> IRCChanUser(id=id, chan=chan, **k)
class IRCActor(ReprSlots, InitSlots):
    __slots__ = ()
    class __metaclass__(type):
        def __call__(cls, *args, **kwds):
            if cls is IRCActor: return cls._IRCActor__cls_call(*args, **kwds)
            return super(IRCActor.__metaclass__, cls).__call__(*args, **kwds)
    @classmethod
    def __cls_call(cls, sender, chan=None, **kwds):
        return IRCServer(name=sender, **kwds) if isinstance(sender, str) else \
               IRCUser(id=sender, **kwds)     if chan is None else \
               IRCChanUser(id=sender, chan=chan, **kwds)

class IRCServer(IRCActor):
    __slots__ = 'name'

class IRCUser(IRCActor):
    __slots__ = 'id', 'is_bot'
    def __init__(self, id=None, nick=None, is_bot=None, **kwds):
        super(IRCUser, self).__init__(**kwds)
        if id is None:
            assert nick is not None
            rec = identity.track_id.get(nick.lower())
            self.id = rec.id if rec and rec.id else ID(nick, None, None)
        else: self.id = id
        if is_bot is None and self.id is not None and link.installed_modes:
            bot_nick = link.installed_modes[0].nick
            self.is_bot = self.id.nick.lower() == bot_nick.lower()
        else: self.is_bot = is_bot

class IRCChanUser(IRCUser):
    __slots__ = 'modes', 'prefix'
    def __init__(self, modes=None, prefix=None, chan=None, **kwds):
        super(IRCChanUser, self).__init__(**kwds)
        if modes is None and chan is not None:
            chan_umodes = channel.umode_channels[chan.lower()]
            self.modes = chan_umodes.get(self.id.nick.lower()) 
        else: self.modes = modes
        if prefix is None and self.modes is not None and link.installed_modes:
            bot = link.installed_modes[0]
            self.prefix = channel.modes_prefix(bot, self.id.nick, self.modes)
        else: self.prefix = prefix

#===============================================================================
# Abstract event classes:
#===============================================================================

class Event(ReprSlots, InitSlots):
    __metaclass__ = AbstractSlots
    __slots__ = 'time' # UNIX timestamp in seconds when the event occurred.

    # Class attribute: a sequence of names (or a single name) of Untwisted
    # events which may trigger the instantiation of this Event.
    links = ()

    def __init__(self, time=None, **kwds):
        super(Event, self).__init__(**kwds)
        self.time = m_time.time() if time is None else time

    # Register Untwisted event handlers in the given Mode instance which shall
    # pass their event arguments to 'link_new', and, if it returns non-None,
    # call 'cont' with the resulting Event instance.
    @classmethod
    def link(cls, mode, cont):
        def event_link_handler(*args, **kwds):
            event = cls.link_new(*args, **kwds)
            if event is not None: cont(event)
        links = cls.links if hasattr(cls.links, '__iter__') else (cls.links,)
        for event_link in links:
            mode.link(event_link, event_link_handler)
        def event_unlink():
            for event_link in links:
                mode.unlink(event_link, event_link_handler)
        return event_unlink

    # Construct and return an Event instance from the given Untwisted event
    # arguments, or return None if the arguments do not match.
    @classmethod
    def link_new(cls, *args, **kwds):
        raise NotImplementedError('Must be overridden by a subclass.')

class IRCMsg(Event):
    __metaclass__ = AbstractSlots
    __slots__ = 'sender'

class IRCChanMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'chan'

class IRCUserMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'target_user'

class IRCTextMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'text'

#===============================================================================
# Events:
#===============================================================================

class Nick(IRCMsg):
    __slots__ = 'new_nick'

    links = 'SOME_NICK'
    link_new = classmethod(lambda cls, _bot, id, nn:
               cls(sender=IRCActor(id), new_nick=nn))

class ChanNick(Nick, IRCChanMsg):
    links = 'SOME_NICK_CHAN'
    link_new = classmethod(lambda cls, _bot, id, nn, ch:
               cls(sender=IRCActor(id, ch), new_nick=nn, chan=ch))

class Quit(IRCTextMsg):
    links = 'OTHER_QUIT'
    link_new = classmethod(lambda cls, _bot, id, msg:
               cls(sender=IRCActor(id), text=msg))

class ChanQuit(Quit, IRCChanMsg):
    links = 'OTHER_QUIT_CHAN'
    link_new = classmethod(lambda cls, _bot, id, msg, ch:
               cls(sender=IRCActor(id, ch), text=msg, chan=ch))

class Join(IRCChanMsg):
    links = 'SOME_JOIN'
    link_new = classmethod(lambda cls, _bot, id, ch:
               cls(sender=IRCActor(id, ch), chan=ch))

class Part(IRCChanMsg, IRCTextMsg):
    links = 'SOME_PART'
    link_new = classmethod(lambda cls, _bot, ch, msg:
               cls(sender=IRCActor(id, ch), chan=ch, text=msg))

class Mode(IRCChanMsg):
    __slots__ = 'params'

    links = 'MODE'
    link_new = classmethod(lambda cls, _bot, src, ch, *params:
               cls(sender=IRCActor(src, ch), chan=ch, params=params))

class Topic(IRCChanMsg, IRCTextMsg):
    links = 'CHAN_TOPIC'
    link_new = classmethod(lambda cls, _bot, ch, topic:
               cls(sender=IRCActor(id, ch), chan=ch, text=topic))

class Invite(IRCChanMsg, IRCUserMsg):
    links = 'INVITE'
    link_new = classmethod(lambda cls, _bot, src, tgt, ch, *_args:
               cls(sender=IRCActor(src, ch), chan=ch, target_user=tgt))

class Kick(IRCChanMsg, IRCUserMsg, IRCTextMsg):
    links = 'SOME_KICKED'
    link_new = classmethod(lambda cls, _bot, tgt, src, ch, msg:
               cls(sender=IRCActor(src, ch), chan=ch, text=msg,
                   target_user=IRCActor(tgt)))

class UserTextMsg(IRCUserMsg, IRCTextMsg):
    link_new = classmethod(lambda cls, _bot, src, tgt, msg, *_args:
               cls(sender=IRCActor(src), target_user=IRCActor(tgt), text=msg)
               if not target.startswith('#') else None)

class ChanTextMsg(IRCChanMsg, IRCTextMsg):
    link_new = classmethod(lambda cls, _bot, src, ch, msg, *_args:
               cls(sender=IRCActor(src, ch), chan=ch, text=msg)
               if tgt.startswith('#') else None)

class UserPrivMsg(UserTextMsg):
    links = 'PRIVMSG'

class ChanPrivMsg(ChanTextMsg):
    links = 'PRIVMSG'

class UserNotice(UserPrivMsg):
    links = 'NOTICE'

class ChanNotice(ChanPrivMsg):
    links = 'NOTICE'

