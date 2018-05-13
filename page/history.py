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
        if '__slots__' in dict:
            slots.extend(a for a in dict['__slots__'] if a not in slots)

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
# and __type__ name, similar to that of collections.namedtuple.
class ReprSlots(object):
    __slots__ = ()
    def __repr__(self):
        slots = (a for a in self.__slots(self) if hasattr(self, a))
        attrs = ('%s=%r' % (a, getattr(self, a)) for a in slots)
        return '%s(%s)' % (type(self).__name__, ', '.join(attrs))

    @classmethod
    def __slots(cls, inst, seen=None):
        if seen is None: seen = set()
        for base in type(inst).__bases__:
            if base in seen: continue
            seen.add(base)
            for slot in cls.__slots(base, seen): yield slot
        if not hasattr(inst, '__slots__'): return
        for slot in inst.__slots__:
            if slot in seen: continue
            yield slot
            seen.add(slot)

#===============================================================================
# Miscellaneous data classes:
#===============================================================================

# IRCSender(name, **k)     -> IRCServer(name=name, **k)
# IRCSender(id, **k)       -> IRCUser(id=id, **k)
# IRCSender(id, chan, **k) -> IRCChanUser(id=id, chan=chan, **k)
class IRCSender(ReprSlots):
    __slots__ = ()
    class __metaclass__(type):
        def __call__(cls, *args, **kwds):
            if cls is IRCSender: return cls._IRCSender__cls_call(*args, **kwds)
            return super(IRCSender.__metaclass__, cls).__call__(*args, **kwds)
    @classmethod
    def __cls_call(cls, sender, chan=None, **kwds):
        return IRCServer(name=sender, **kwds) if isinstance(sender, str) else \
               IRCUser(id=sender, **kwds)     if chan is None else \
               IRCChanUser(id=sender, chan=chan, **kwds)

class IRCServer(IRCSender):
    __slots__ = 'name',
    def __init__(self, name, **kwds):
        super(IRCServer, self).__init__(**kwds)
        self.name = name

class IRCUser(IRCSender):
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

class Event(ReprSlots):
    __metaclass__ = AbstractSlots
    __slots__ = 'time', # UNIX timestamp in seconds when the event occurred.

    # Class attribute: a sequence of names of Untwisted events which may trigger
    # the instantiation of this Event.
    links = ()

    def __init__(self, time=None):
        self.time = m_time.time() if time is None else time

    # Register Untwisted event handlers in the given Mode instance which shall
    # pass their event arguments to 'link_new', and, if it returns non-None,
    # call 'cont' with the resulting Event instance.
    @classmethod
    def link(cls, mode, cont):
        def event_link_handler(*args, **kwds):
            event = cls.link_new(*args, **kwds)
            if event is not None: cont(event)
        for event_link in cls.links:
            mode.link(event_link, event_link_handler)
        def event_unlink():
            for event_link in cls.links:
                mode.unlink(event_link, event_link_handler)
        return event_unlink

    # Construct and return an Event instance from the given Untwisted event
    # arguments, or return None if the arguments do not match.
    @classmethod
    def link_new(cls, *args, **kwds):
        raise NotImplementedError('Must be overridden by a subclass.')

class IRCMsg(Event):
    __metaclass__ = AbstractSlots
    __slots__ = 'sender',
    def __init__(self, sender, **kwds):
        super(IRCMsg, self).__init__(**kwds)
        self.sender = sender

class IRCChanMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'chan',
    def __init__(self, chan, **kwds):
        super(IRCChanMsg, self).__init__(**kwds)
        self.chan = chan

class IRCUserMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'target_user',
    def __init__(self, target_user, **kwds):
        super(IRCUserMsg, self).__init__(**kwds)
        self.target_user = target_user

class IRCTextMsg(IRCMsg):
    __metaclass__ = AbstractSlots
    __slots__ = 'text',
    def __init__(self, text, **kwds):
        super(IRCTextMsg, self).__init__(**kwds)
        self.text = text

#===============================================================================
# Events:
#===============================================================================

class Nick(IRCMsg):
    __slots__ = 'new_nick',
    def __init__(self, new_nick, **kwds):
        super(Nick, self).__init__(**kwds)
        self.new_nick = new_nick

    links = 'SOME_NICK',
    link_new = classmethod(lambda cls, _bot, id, nn:
               cls(sender=IRCSender(id), new_nick=nn))

class ChanNick(Nick, IRCChanMsg):
    links = 'SOME_NICK_CHAN',
    link_new = classmethod(lambda cls, _bot, id, nn, ch:
               cls(sender=IRCSender(id, ch), new_nick=nn, chan=ch))

class Quit(IRCTextMsg):
    links = 'OTHER_QUIT',
    link_new = classmethod(lambda cls, _bot, id, msg:
               cls(sender=IRCSender(id), text=msg))

class ChanQuit(Quit, IRCChanMsg):
    links = 'OTHER_QUIT_CHAN',
    link_new = classmethod(lambda cls, _bot, id, msg, ch:
               cls(sender=IRCSender(id, ch), text=msg, chan=ch))

class Join(IRCChanMsg):
    links = 'SOME_JOIN'
    link_new = classmethod(lambda cls, _bot, id, ch:
               cls(sender=IRCSender(id, ch), chan=ch))

class Part(IRCChanMsg, IRCTextMsg):
    links = 'SOME_PART'
    link_new = classmethod(lambda cls, _bot, ch, msg:
               cls(sender=IRCSender(id, ch), chan=ch, text=msg))

class Mode(IRCChanMsg):
    __slots__ = 'modes', 'params'
    def __init__(self, modes, *params, **kwds):
        super(IRCChanMsg, self).__init__(**kwds)
        self.modes = modes
        self.params = params

class Topic(IRCChanMsg, IRCTextMsg):
    links = 'CHAN_TOPIC'
    link_new = classmethod(lambda cls, _bot, ch, topic:
               cls(sender=IRCSender(id, ch), chan=ch, text=topic))

class Invite(IRCChanMsg, IRCUserMsg):
    pass

class Kick(IRCChanMsg, IRCUserMsg, IRCTextMsg):
    pass

class Message(IRCChanMsg, IRCTextMsg):
    pass

class Notice(IRCChanMsg, IRCTextMsg):
    pass

