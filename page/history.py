from __future__ import print_function

from collections import OrderedDict
import time as m_time

from util import NotInstalled, AlreadyInstalled
from history_util import *
import identity
import channel

installed_modes = []

def install(bot):
    if bot in installed_modes: raise AlreadyInstalled
    installed_modes.append(bot)

def uninstall(bot):
    if bot not in installed_modes: raise NotInstalled
    installed_modes.remove(bot)

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
    __slots__ = 'id', 'is_self'
    def __init__(self, arg=None, id=None, nick=None, is_self=None, **kwds):
        assert arg is None or id is None and nick is None
        nick = arg if nick is None and isinstance(arg, str) else nick
        id = arg if id is None and not isinstance(arg, str) else id

        super(IRCUser, self).__init__(id=id, is_self=is_self, **kwds)
        if id is None:
            assert nick is not None
            rec = identity.track_id.get(nick.lower())
            self.id = rec.id if rec and rec.id else ID(nick, None, None)
        if is_self is None and self.id is not None and installed_modes:
            own_nick = next(iter(installed_modes)).nick
            self.is_self = self.id.nick.lower() == own_nick.lower()

class IRCChanUser(IRCUser):
    __slots__ = 'modes', 'prefix'
    def __init__(self, modes=None, prefix=None, chan=None, **kwds):
        super(IRCChanUser, self).__init__(modes=modes, prefix=prefix, **kwds)
        if modes is None and chan is not None:
            chan_umodes = channel.umode_channels[chan.lower()]
            self.modes = chan_umodes.get(self.id.nick.lower()) 
        if prefix is None and self.modes is not None and installed_modes:
            bot = next(iter(installed_modes))
            self.prefix = channel.modes_prefix(bot, self.modes)

#===============================================================================
# Abstract event classes:
#===============================================================================

class Event(ReprSlots, InitSlots):
    __metaclass__ = type('EventClass', (AbstractSlots, SubclassRecorder), {})
    __slots__ = 'time' # UNIX timestamp in seconds when the event occurred.

    # Class attribute: a sequence of names (or a single name) of Untwisted
    # events which may trigger the instantiation of this Event.
    links = None

    def __init__(self, time=None, **kwds):
        super(Event, self).__init__(time=time, **kwds)
        if time is None: self.time = m_time.time()

    # Register Untwisted event handlers in the given Mode instance which shall
    # pass their event arguments to 'link_new', and, if it returns non-None,
    # call 'cont' with the resulting Event instance; or, if 'links' is None,
    # do the same for all direct subclasses. Return a function which# when
    # called removes all such event handlers set.
    @classmethod
    def link(cls, mode, cont, seen=None):
        if cls.links is None:
            if seen is None: seen = set()
            unlink_funcs = []
            for subcls in cls._subclasses:
                if subcls in seen: continue
                unlink_funcs.append(subcls.link(mode, cont, seen))
            def event_unlink():
                for unlink_func in unlink_funcs: unlink_func()
        else:
            def event_link_handler(*args, **kwds):
                event = cls.link_new(*args, **kwds)
                if event is not None: cont(event)
            links = cls.links if hasattr(cls.links, '__iter__') else (cls.links,)
            for event_link in links:
                mode.link(event_link, event_link_handler)
            def event_unlink():
                for event_link in links:
                    mode.unlink(event_link, event_link_handler)
        if seen is not None: seen.add(cls)
        return event_unlink

    # Construct and return an Event instance from the given Untwisted event
    # arguments, or return None if the arguments do not match.
    @classmethod
    def link_new(cls, *args, **kwds):
        raise NotImplementedError('Must be overridden by a subclass.')

class IRCMsg(Event):
    __metaclass__ = Event.__metaclass__
    __slots__ = 'sender'

class IRCChanMsg(IRCMsg):
    __metaclass__ = IRCMsg.__metaclass__
    __slots__ = 'chan'

class IRCUserMsg(IRCMsg):
    __metaclass__ = IRCMsg.__metaclass__
    __slots__ = 'target_user'

class IRCTextMsg(IRCMsg):
    __metaclass__ = IRCMsg.__metaclass__
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
    link_new = classmethod(lambda cls, _bot, id, ch, msg:
               cls(sender=IRCActor(id, ch), chan=ch, text=msg))

class Mode(IRCChanMsg):
    __slots__ = 'params'

    links = 'MODE'
    link_new = classmethod(lambda cls, _bot, src, ch, *params:
               cls(sender=IRCActor(src, ch), chan=ch, params=params))

class Topic(IRCChanMsg, IRCTextMsg):
    links = 'TOPIC'
    link_new = classmethod(lambda cls, _bot, src, ch, topic:
               cls(sender=IRCActor(src, ch), chan=ch, text=topic))

class Invite(IRCChanMsg, IRCUserMsg):
    links = 'INVITE'
    link_new = classmethod(lambda cls, _bot, src, tgt, ch, *_args:
               cls(sender=IRCActor(src, ch), chan=ch,
                   target_user=IRCUser(tgt)))

class Kick(IRCChanMsg, IRCUserMsg, IRCTextMsg):
    links = 'SOME_KICKED'
    link_new = classmethod(lambda cls, _bot, tgt, src, ch, msg:
               cls(sender=IRCActor(src, ch), chan=ch, text=msg,
                   target_user=IRCUser(tgt)))

class UserTextMsg(IRCUserMsg, IRCTextMsg):
    link_new = classmethod(lambda cls, _bot, src, tgt, msg, *_args:
               cls(sender=IRCActor(src), target_user=IRCUser(tgt), text=msg)
               if not tgt.startswith('#') else None)

class ChanTextMsg(IRCChanMsg, IRCTextMsg):
    link_new = classmethod(lambda cls, _bot, src, tgt, msg, *_args:
               cls(sender=IRCActor(src, tgt), chan=tgt, text=msg)
               if tgt.startswith('#') else None)

class UserPrivMsg(UserTextMsg):
    links = 'PRIVMSG'

class ChanPrivMsg(ChanTextMsg):
    links = 'PRIVMSG'

class UserNotice(UserTextMsg):
    links = 'NOTICE'

class ChanNotice(ChanTextMsg):
    links = 'NOTICE'
